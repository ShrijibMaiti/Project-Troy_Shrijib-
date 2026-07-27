"""
SHA-256 hash chain over the signals table.

    row_hash = sha256(prev_hash || canonical_json(payload))

Properties:
  - Any edit to a row changes its hash, which breaks every subsequent link.
  - The head hash is published on every export, so a third party who kept an
    old export can detect retroactive tampering without DB access.
  - Verification is a linear walk. No trusted third party required.

CONCURRENCY: two parallel inserts must not read the same head. We take a
Postgres transaction-scoped advisory lock around the read-head/compute/insert
sequence. It serialises only signal appends, which is fine — capture is
I/O-bound, not insert-bound.

DO NOT change Signal.hash_payload() or the canonicalisation below without a
documented migration that re-anchors the chain. Changing either invalidates
every hash ever computed.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.signal import Signal

GENESIS_HASH = "0" * 64

# Arbitrary but FIXED. Must not collide with other advisory locks in the app.
_CHAIN_ADVISORY_LOCK_KEY = 8_314_207_001


def canonical_json(payload: dict) -> str:
    """
    Canonical form. Sorted keys, no insignificant whitespace, UTF-8, no NaN.
    Two structurally identical payloads must always produce the same bytes.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    )


def compute_row_hash(payload: dict, prev_hash: str) -> str:
    if len(prev_hash) != 64:
        raise ValueError(f"prev_hash must be 64 hex chars, got {len(prev_hash)}")
    material = prev_hash + canonical_json(payload)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def _acquire_chain_lock(session: AsyncSession) -> None:
    """Transaction-scoped. Released automatically on commit or rollback."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:k)"), {"k": _CHAIN_ADVISORY_LOCK_KEY}
    )


async def get_head(session: AsyncSession) -> tuple[int, str]:
    """Returns (chain_seq, row_hash) of the newest link, or (0, GENESIS)."""
    stmt = (
        select(Signal.chain_seq, Signal.row_hash)
        .order_by(Signal.chain_seq.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return 0, GENESIS_HASH
    return int(row[0]), str(row[1])


async def append_signal(session: AsyncSession, signal: Signal) -> Signal:
    """
    Link a Signal into the chain and add it to the session.

    Caller is responsible for the commit. The advisory lock is held until that
    commit, which is what guarantees no two signals share a prev_hash.
    """
    await _acquire_chain_lock(session)
    _, head_hash = await get_head(session)

    # CRITICAL: id must exist BEFORE hashing.
    # Signal.id uses default=uuid.uuid4, which SQLAlchemy applies at FLUSH
    # time — so without this line the hash covers "id": null, and every
    # recomputation after flush produces a different hash. Assigning it here
    # makes the hashed payload identical to the persisted row.
    if signal.id is None:
        signal.id = uuid.uuid4()

    signal.prev_hash = head_hash
    signal.row_hash = compute_row_hash(signal.hash_payload(), head_hash)

    session.add(signal)
    await session.flush()

    # chain_seq is filled by a server-side nextval() default. SQLAlchemy does
    # not return it on INSERT, so the attribute is expired — and touching an
    # expired attribute under asyncpg raises MissingGreenlet. Refresh it
    # explicitly while we are still in async context.
    await session.refresh(signal, ["chain_seq"])

    return signal


@dataclass
class ChainVerificationResult:
    ok: bool
    checked: int
    head_seq: int
    head_hash: str
    first_break_seq: int | None = None
    first_break_id: str | None = None
    reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "checked": self.checked,
            "head_seq": self.head_seq,
            "head_hash": self.head_hash,
            "first_break_seq": self.first_break_seq,
            "first_break_id": self.first_break_id,
            "reason": self.reason,
        }


async def verify_chain(
    session: AsyncSession,
    start_seq: int = 0,
    batch_size: int = 1000,
) -> ChainVerificationResult:
    """
    Walk the chain in order and recompute every hash.

    Reports the FIRST break, because everything after a break is untrustworthy
    anyway and a list of thousands of downstream failures is noise.
    """
    prev_hash = GENESIS_HASH
    checked = 0
    head_seq = 0
    head_hash = GENESIS_HASH
    cursor = start_seq

    if start_seq > 0:
        anchor = (
            await session.execute(
                select(Signal.row_hash).where(Signal.chain_seq == start_seq).limit(1)
            )
        ).scalar_one_or_none()
        if anchor is None:
            return ChainVerificationResult(
                ok=False,
                checked=0,
                head_seq=0,
                head_hash=GENESIS_HASH,
                reason=f"anchor chain_seq={start_seq} not found",
            )
        prev_hash = anchor

    while True:
        stmt = (
            select(Signal)
            .where(Signal.chain_seq > cursor)
            .order_by(Signal.chain_seq.asc())
            .limit(batch_size)
        )
        rows = list((await session.execute(stmt)).scalars())
        if not rows:
            break

        for sig in rows:
            if sig.prev_hash != prev_hash:
                return ChainVerificationResult(
                    ok=False,
                    checked=checked,
                    head_seq=head_seq,
                    head_hash=head_hash,
                    first_break_seq=sig.chain_seq,
                    first_break_id=str(sig.id),
                    reason="prev_hash does not match previous row_hash "
                    "(row inserted, deleted or reordered)",
                )

            expected = compute_row_hash(sig.hash_payload(), sig.prev_hash)
            if expected != sig.row_hash:
                return ChainVerificationResult(
                    ok=False,
                    checked=checked,
                    head_seq=head_seq,
                    head_hash=head_hash,
                    first_break_seq=sig.chain_seq,
                    first_break_id=str(sig.id),
                    reason="row_hash does not match content (row was modified)",
                )

            prev_hash = sig.row_hash
            head_seq = sig.chain_seq
            head_hash = sig.row_hash
            checked += 1
            cursor = sig.chain_seq

    return ChainVerificationResult(
        ok=True, checked=checked, head_seq=head_seq, head_hash=head_hash
    )


async def head_hash_for_export(session: AsyncSession) -> str:
    """Printed on every exported PDF and register file."""
    _, h = await get_head(session)
    return h
