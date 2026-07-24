"""
End-to-end smoke test for Domain 5 evidence integrity.

Proves, in order:
  1. Signals append and the hash chain links correctly.
  2. verify_chain() passes on an untampered chain.
  3. The PRIVILEGE layer blocks the application role (troy_app).
  3b. The TRIGGER layer blocks the owner role (troy_owner) independently —
      full UPDATE rights, still refused. This is the defence that matters,
      because privileges drift and triggers do not.
  4. Crypto-shredding round-trips, and erasure makes the plaintext
     permanently unrecoverable WITHOUT invalidating the hash chain.
     Runs while the chain is still intact so the comparison is meaningful.
  5. A tampered row is DETECTED, at the correct chain_seq, with the correct
     reason (content modified).
  6. A DELETED row is detected as a chain break at its ORPHANED SUCCESSOR,
     not silently ignored.

Tampering is done as troy_owner with the trigger explicitly disabled. That is
deliberate: it demonstrates that corrupting the store requires DB-admin access
AND an explicit, loggable act — and that even then, the chain still catches it.

Run:  python scripts/smoke_hash_chain.py
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from db.integrity.crypto_shred import (
    ShreddedField,
    SubjectKey,
    decrypt_field,
    encrypt_field,
    erase_subject,
)
from db.integrity.hash_chain import (
    append_signal,
    compute_row_hash,
    get_head,
    verify_chain,
)
from db.models.excerpt import Excerpt
from db.models.org import Org
from db.models.signal import Signal, SignalMetric, SignalSource
from db.models.vendor import EntityType, Vendor
from db.session import SessionFactory, dispose_engine

# psycopg2 engine as troy_owner — used only for tampering and teardown.
OWNER_URL = os.environ.get("SYNC_DATABASE_URL") or os.environ[
    "DATABASE_OWNER_URL"
].replace("postgresql+asyncpg://", "postgresql://")
owner_engine = create_engine(OWNER_URL, future=True)

MARKER = "SMOKE-TEST"


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

PASS, FAIL, INFO = "  [PASS]", "  [FAIL]", "  [ .. ]"
failures: list[str] = []


def step(title: str) -> None:
    print(f"\n=== {title} " + "=" * max(0, 66 - len(title)))


def check(condition: bool, label: str, detail: str = "") -> None:
    if condition:
        print(f"{PASS} {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"{FAIL} {label}" + (f" — {detail}" if detail else ""))
        failures.append(label)


def info(msg: str) -> None:
    print(f"{INFO} {msg}")


# ---------------------------------------------------------------------------
# Owner-level operations (bypass the app role's restrictions)
# ---------------------------------------------------------------------------

def owner_exec(sql: str, **params) -> None:
    """Run as troy_owner with all guards ACTIVE. Used to prove the trigger."""
    with owner_engine.begin() as conn:
        conn.execute(text(sql), params)


def with_trigger_disabled(sql: str, **params) -> None:
    """
    Tampering requires explicitly disabling the guard. Even as owner, the
    trigger fires — so corruption cannot be accidental.
    """
    with owner_engine.begin() as conn:
        conn.execute(text("ALTER TABLE signals DISABLE TRIGGER trg_signals_append_only"))
        try:
            conn.execute(text(sql), params)
        finally:
            conn.execute(
                text("ALTER TABLE signals ENABLE TRIGGER trg_signals_append_only")
            )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_dedup_key(vendor_id: uuid.UUID, url: str, d: date, metric: str) -> str:
    raw = f"{vendor_id}|{url}|{d.isoformat()}|{metric}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def seed_org_and_vendor(session) -> tuple[Org, Vendor]:
    org = Org(
        clerk_org_id=f"{MARKER}-org-{uuid.uuid4().hex[:8]}",
        name=f"{MARKER} Bank",
        home_country="IE",
    )
    session.add(org)
    await session.flush()

    vendor = Vendor(
        lei="SMOKE00000000000TEST",
        legal_name=f"{MARKER} Vendor Ltd",
        display_name=f"{MARKER} Vendor",
        entity_type=EntityType.PRIVATE,
        org_id=org.id,
    )
    session.add(vendor)
    await session.flush()
    return org, vendor


async def make_excerpt(session, url: str, body: str) -> Excerpt:
    ex = Excerpt(
        source_url=url,
        archive_url=f"https://web.archive.org/web/2026/{url}",
        source_domain="example.com",
        source_title=f"{MARKER} article",
        text=body,
        char_count=len(body),
        published_at=datetime.now(timezone.utc),
        retrieved_at=datetime.now(timezone.utc),
        content_sha256=hashlib.sha256(body.encode()).hexdigest(),
    )
    session.add(ex)
    await session.flush()
    return ex


async def make_signal(session, vendor: Vendor, n: int) -> Signal:
    url = f"https://example.com/{MARKER.lower()}/{n}"
    body = f"{MARKER}: source excerpt number {n} about the vendor."
    ex = await make_excerpt(session, url, body)

    event_day = date.today() - timedelta(days=10 - n)
    metric = [
        SignalMetric.LEADERSHIP_CHANGE,
        SignalMetric.LEGAL_EVENT,
        SignalMetric.HEADCOUNT_CHANGE,
    ][n - 1]

    sig = Signal(
        vendor_id=vendor.id,
        metric=metric,
        source=SignalSource.MANUAL,
        event_date=event_day,
        observed_at=datetime.now(timezone.utc),
        value=float(n),
        summary=f"{MARKER} signal {n}",
        payload={"role": "CFO", "direction": "departure", "n": n},
        excerpt_id=ex.id,
        source_url=url,
        archive_url=ex.archive_url,
        validator_verdict="accepted",
        validator_confidence=0.91,
        validator_model_id="claude-sonnet-4-6",
        validator_prompt_hash="a" * 64,
        dedup_key=make_dedup_key(vendor.id, url, event_day, metric.value),
    )
    return await append_signal(session, sig)


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------

def teardown() -> None:
    """
    Remove all smoke-test data.

    Only our OWN named triggers are disabled. `DISABLE TRIGGER ALL` would also
    hit Postgres's internal RI_ConstraintTrigger_* foreign-key triggers, which
    requires superuser — and disabling FK enforcement is not something we want
    to do even when we can.
    """
    guards = [
        ("signals", "trg_signals_append_only"),
        ("excerpts", "trg_excerpts_append_only"),
        ("shredded_fields", "trg_shredded_fields_append_only"),
        ("subject_keys", "trg_subject_keys_erasure_only"),
    ]

    with owner_engine.begin() as conn:
        for table, trg in guards:
            conn.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER {trg}"))
        try:
            # Order matters: children before parents (FKs stay enforced).
            conn.execute(
                text("DELETE FROM shredded_fields WHERE subject_ref LIKE :m"),
                {"m": f"{MARKER}%"},
            )
            conn.execute(
                text("DELETE FROM subject_keys WHERE subject_ref LIKE :m"),
                {"m": f"{MARKER}%"},
            )
            conn.execute(
                text("DELETE FROM signals WHERE summary LIKE :m"),
                {"m": f"{MARKER}%"},
            )
            conn.execute(
                text("DELETE FROM excerpts WHERE source_title LIKE :m"),
                {"m": f"{MARKER}%"},
            )
            conn.execute(
                text("DELETE FROM vendors WHERE display_name LIKE :m"),
                {"m": f"{MARKER}%"},
            )
            conn.execute(
                text("DELETE FROM orgs WHERE name LIKE :m"), {"m": f"{MARKER}%"}
            )
        finally:
            for table, trg in guards:
                conn.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER {trg}"))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> int:
    print("\n" + "=" * 72)
    print("  TROY — DOMAIN 5 EVIDENCE INTEGRITY SMOKE TEST")
    print("=" * 72)

    teardown()  # clean slate from any prior run

    signal_ids: list[uuid.UUID] = []
    seqs: list[int] = []

    # ---------------------------------------------------------------
    step("1. Append three signals to the chain")
    # ---------------------------------------------------------------
    async with SessionFactory() as session:
        _, vendor = await seed_org_and_vendor(session)

        head_seq_before, head_hash_before = await get_head(session)
        info(f"head before: seq={head_seq_before} hash={head_hash_before[:16]}...")

        prev = head_hash_before
        for n in (1, 2, 3):
            sig = await make_signal(session, vendor, n)
            check(
                sig.prev_hash == prev,
                f"signal {n} links to previous head",
                f"prev={sig.prev_hash[:12]}...",
            )
            expected = compute_row_hash(sig.hash_payload(), sig.prev_hash)
            check(sig.row_hash == expected, f"signal {n} row_hash is correct")
            prev = sig.row_hash
            signal_ids.append(sig.id)
            seqs.append(sig.chain_seq)

        await session.commit()

    check(
        seqs == sorted(seqs) and len(set(seqs)) == 3,
        "chain_seq is monotonic and unique",
        f"seqs={seqs}",
    )

    # ---------------------------------------------------------------
    step("2. Verify the untampered chain")
    # ---------------------------------------------------------------
    async with SessionFactory() as session:
        result = await verify_chain(session)
        check(result.ok, "verify_chain reports OK", f"checked={result.checked}")
        check(result.checked >= 3, "all rows were walked")
        info(f"head hash: {result.head_hash}")

    # ---------------------------------------------------------------
    step("3. Append-only: privilege layer (application role)")
    # ---------------------------------------------------------------
    async with SessionFactory() as session:
        blocked = False
        reason = ""
        try:
            await session.execute(
                text("UPDATE signals SET summary = :s WHERE id = :i"),
                {"s": "tampered", "i": str(signal_ids[1])},
            )
            await session.commit()
        except (DBAPIError, ProgrammingError) as exc:
            blocked = True
            reason = str(exc.orig).split("\n")[0][:90]
            await session.rollback()
        check(blocked, "UPDATE on signals is rejected", reason)

    async with SessionFactory() as session:
        blocked = False
        try:
            await session.execute(
                text("DELETE FROM signals WHERE id = :i"), {"i": str(signal_ids[1])}
            )
            await session.commit()
        except (DBAPIError, ProgrammingError):
            blocked = True
            await session.rollback()
        check(blocked, "DELETE on signals is rejected")

    # ---------------------------------------------------------------
    step("3b. Append-only: trigger layer (owner role, privileges intact)")
    # ---------------------------------------------------------------
    # Step 3 proved the PRIVILEGE layer: troy_app was rejected before the
    # trigger ever ran. This proves the SECOND layer independently — troy_owner
    # has full UPDATE rights and is still blocked, by the trigger alone.
    #
    # This is the defence that matters, because privileges drift over time
    # (a well-meaning GRANT, a restored backup, a new role) and the trigger
    # does not.
    blocked = False
    reason = ""
    try:
        owner_exec(
            "UPDATE signals SET summary = :s WHERE id = :i",
            s="owner tamper attempt",
            i=str(signal_ids[0]),
        )
    except Exception as exc:  # psycopg2 raises through SQLAlchemy
        blocked = True
        reason = str(getattr(exc, "orig", exc)).split("\n")[0][:90]
    check(blocked, "UPDATE as OWNER is blocked by the trigger", reason)

    blocked = False
    try:
        owner_exec("DELETE FROM signals WHERE id = :i", i=str(signal_ids[0]))
    except Exception:
        blocked = True
    check(blocked, "DELETE as OWNER is blocked by the trigger")

    # ---------------------------------------------------------------
    step("4. Crypto-shredding (GDPR Art. 17 vs immutable chain)")
    # ---------------------------------------------------------------
    # Deliberately runs BEFORE the tampering steps, while the chain is still
    # intact — so "erasure did not alter the chain" is proved against a full
    # 3-link walk rather than a chain already broken by a later test.
    subject_ref = f"{MARKER}-" + hashlib.sha256(b"jane.doe|cfo").hexdigest()[:40]
    exec_name = "Jane Doe"

    async with SessionFactory() as session:
        field = await encrypt_field(
            session, signal_ids[0], subject_ref, "exec_name", exec_name
        )
        await session.commit()
        field_id = field.id

    async with SessionFactory() as session:
        field = (
            await session.execute(
                select(ShreddedField).where(ShreddedField.id == field_id)
            )
        ).scalar_one()
        recovered = await decrypt_field(session, field)
        check(recovered == exec_name, "identifier round-trips before erasure")

    async with SessionFactory() as session:
        before = await verify_chain(session)
        check(before.ok, "chain is intact before erasure", f"checked={before.checked}")

    async with SessionFactory() as session:
        done = await erase_subject(session, subject_ref)
        await session.commit()
        check(done, "erase_subject executed")

    async with SessionFactory() as session:
        field = (
            await session.execute(
                select(ShreddedField).where(ShreddedField.id == field_id)
            )
        ).scalar_one()
        recovered = await decrypt_field(session, field)
        check(recovered is None, "identifier is unrecoverable after erasure")

        still_there = (
            await session.execute(
                select(ShreddedField).where(ShreddedField.id == field_id)
            )
        ).scalar_one_or_none()
        check(still_there is not None, "ciphertext row itself is retained")

        after = await verify_chain(session)
        check(
            after.ok and after.checked == before.checked,
            "erasure did NOT alter the hash chain",
            f"checked {before.checked} -> {after.checked}",
        )

    async with SessionFactory() as session:
        key_row = (
            await session.execute(
                select(SubjectKey).where(SubjectKey.subject_ref == subject_ref)
            )
        ).scalar_one()
        check(key_row.erased_at is not None, "subject key is marked erased")
        check(
            set(key_row.wrapped_key) == {0},
            "wrapped key bytes are zeroed, not just flagged",
        )

    # ---------------------------------------------------------------
    step("5. Tamper with the middle row (as owner, trigger disabled)")
    # ---------------------------------------------------------------
    target_id, target_seq = signal_ids[1], seqs[1]
    info(f"tampering with signal 2 (chain_seq={target_seq})")

    with_trigger_disabled(
        "UPDATE signals SET summary = :s WHERE id = :i",
        s=f"{MARKER} signal 2 TAMPERED",
        i=str(target_id),
    )

    async with SessionFactory() as session:
        result = await verify_chain(session)
        check(not result.ok, "verify_chain DETECTS the tamper")
        check(
            result.first_break_seq == target_seq,
            "break reported at the correct chain_seq",
            f"expected={target_seq} got={result.first_break_seq}",
        )
        check(
            result.reason is not None and "modified" in result.reason,
            "reason identifies content modification",
            result.reason or "",
        )
        info(f"rows verified before break: {result.checked}")

    # restore so the next test starts from a valid chain
    with_trigger_disabled(
        "UPDATE signals SET summary = :s WHERE id = :i",
        s=f"{MARKER} signal 2",
        i=str(target_id),
    )
    async with SessionFactory() as session:
        result = await verify_chain(session)
        check(result.ok, "chain is valid again after restoring content")

    # ---------------------------------------------------------------
    step("6. Delete a row (as owner) — chain must notice the hole")
    # ---------------------------------------------------------------
    with owner_engine.begin() as conn:
        conn.execute(
            text("ALTER TABLE signals DISABLE TRIGGER trg_signals_append_only")
        )
        conn.execute(
            text(
                "ALTER TABLE shredded_fields "
                "DISABLE TRIGGER trg_shredded_fields_append_only"
            )
        )
        conn.execute(
            text("DELETE FROM shredded_fields WHERE signal_id = :i"),
            {"i": str(target_id)},
        )
        conn.execute(text("DELETE FROM signals WHERE id = :i"), {"i": str(target_id)})
        conn.execute(
            text(
                "ALTER TABLE shredded_fields "
                "ENABLE TRIGGER trg_shredded_fields_append_only"
            )
        )
        conn.execute(
            text("ALTER TABLE signals ENABLE TRIGGER trg_signals_append_only")
        )

    async with SessionFactory() as session:
        result = await verify_chain(session)
        check(not result.ok, "verify_chain DETECTS the deletion")
        check(
            result.first_break_seq == seqs[2],
            "break reported at the orphaned successor",
            f"expected={seqs[2]} got={result.first_break_seq}",
        )
        check(
            result.reason is not None and "prev_hash" in result.reason,
            "reason identifies a broken link",
            result.reason or "",
        )

    # ---------------------------------------------------------------
    step("Teardown")
    # ---------------------------------------------------------------
    teardown()
    async with SessionFactory() as session:
        remaining = (
            await session.execute(
                select(Signal).where(Signal.summary.like(f"{MARKER}%"))
            )
        ).scalars().all()
        check(len(remaining) == 0, "test data removed")

    await dispose_engine()
    owner_engine.dispose()

    print("\n" + "=" * 72)
    if failures:
        print(f"  RESULT: {len(failures)} FAILURE(S)")
        for f in failures:
            print(f"    - {f}")
        print("=" * 72 + "\n")
        return 1
    print("  RESULT: ALL CHECKS PASSED")
    print("=" * 72 + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))