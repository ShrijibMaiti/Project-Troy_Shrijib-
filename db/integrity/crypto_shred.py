"""
GDPR Article 17 vs. an immutable audit log.

The conflict: we never delete signals (evidence integrity), but named
executives have a right to erasure.

The resolution: crypto-shredding. The person's identifier is never stored in
plaintext. It is encrypted with a per-subject data key (AES-256-GCM); the data
key itself is stored wrapped by a master key. Erasure = destroy the wrapped
data key row. The signal, its timestamp, its score contribution and its place
in the hash chain all survive untouched — only the identifier becomes
permanently unrecoverable.

This works with the hash chain because the CIPHERTEXT is what gets hashed, and
the ciphertext never changes. Destroying the key does not alter any hashed row.

Storage rule: role + event only. Never biography, contact details or inferred
characteristics. See compliance/lia.md.
"""

from __future__ import annotations

import base64
import os
import uuid
from datetime import datetime

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import DateTime, Index, LargeBinary, String, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

# 32 raw bytes, base64-encoded in the environment. Rotate via re-wrapping.
_MASTER_KEY_B64 = os.environ.get("SHRED_MASTER_KEY")
NONCE_BYTES = 12


def _master_key() -> bytes:
    if not _MASTER_KEY_B64:
        raise RuntimeError("SHRED_MASTER_KEY is not set")
    key = base64.b64decode(_MASTER_KEY_B64)
    if len(key) != 32:
        raise RuntimeError("SHRED_MASTER_KEY must decode to exactly 32 bytes")
    return key


class SubjectKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """
    One wrapped data key per data subject.

    DELETING A ROW HERE IS THE ERASURE. It is the only intentional DELETE in
    this entire domain, and it is the mechanism that makes "we never delete"
    and "you have a right to erasure" both true at the same time.
    """

    __tablename__ = "subject_keys"

    # Stable pseudonymous handle, e.g. sha256(lower(name)+vendor_id).
    # Never the name itself.
    subject_ref: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    wrapped_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrap_nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_subject_keys_ref", "subject_ref"),)


class ShreddedField(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """
    An encrypted identifier attached to a signal.

    The signal row itself stores only `subject_ref` inside its JSONB payload,
    never plaintext — so the hashed content contains no personal data.
    """

    __tablename__ = "shredded_fields"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False, index=True
    )
    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "exec_name"

    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


# --------------------------------------------------------------------------
# Key management
# --------------------------------------------------------------------------

def _wrap(data_key: bytes) -> tuple[bytes, bytes]:
    nonce = os.urandom(NONCE_BYTES)
    wrapped = AESGCM(_master_key()).encrypt(nonce, data_key, b"troy-subject-key")
    return wrapped, nonce


def _unwrap(wrapped: bytes, nonce: bytes) -> bytes:
    return AESGCM(_master_key()).decrypt(nonce, wrapped, b"troy-subject-key")


async def get_or_create_subject_key(
    session: AsyncSession, subject_ref: str
) -> bytes | None:
    """Returns the raw data key, or None if the subject has been erased."""
    existing = (
        await session.execute(
            select(SubjectKey).where(SubjectKey.subject_ref == subject_ref)
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.erased_at is not None:
            return None
        return _unwrap(existing.wrapped_key, existing.wrap_nonce)

    data_key = AESGCM.generate_key(bit_length=256)
    wrapped, nonce = _wrap(data_key)
    session.add(
        SubjectKey(subject_ref=subject_ref, wrapped_key=wrapped, wrap_nonce=nonce)
    )
    await session.flush()
    return data_key


# --------------------------------------------------------------------------
# Encrypt / decrypt
# --------------------------------------------------------------------------

async def encrypt_field(
    session: AsyncSession,
    signal_id: uuid.UUID,
    subject_ref: str,
    field_name: str,
    plaintext: str,
) -> ShreddedField:
    data_key = await get_or_create_subject_key(session, subject_ref)
    if data_key is None:
        raise ValueError(f"subject {subject_ref} has been erased; cannot re-encrypt")

    nonce = os.urandom(NONCE_BYTES)
    ct = AESGCM(data_key).encrypt(
        nonce, plaintext.encode("utf-8"), subject_ref.encode("utf-8")
    )
    field = ShreddedField(
        signal_id=signal_id,
        subject_ref=subject_ref,
        field_name=field_name,
        ciphertext=ct,
        nonce=nonce,
    )
    session.add(field)
    return field


async def decrypt_field(session: AsyncSession, field: ShreddedField) -> str | None:
    """Returns None when the subject has been erased. Callers render '[erased]'."""
    key_row = (
        await session.execute(
            select(SubjectKey).where(SubjectKey.subject_ref == field.subject_ref)
        )
    ).scalar_one_or_none()

    if key_row is None or key_row.erased_at is not None:
        return None

    data_key = _unwrap(key_row.wrapped_key, key_row.wrap_nonce)
    plaintext = AESGCM(data_key).decrypt(
        field.nonce, field.ciphertext, field.subject_ref.encode("utf-8")
    )
    return plaintext.decode("utf-8")


# --------------------------------------------------------------------------
# THE ERASURE
# --------------------------------------------------------------------------

async def erase_subject(session: AsyncSession, subject_ref: str) -> bool:
    """
    Execute a right-to-erasure request.

    Destroys the wrapped data key. Every ciphertext for this subject becomes
    permanently undecryptable. No signal row is touched, so the hash chain
    remains valid and verifiable.

    Caller must write an AuditLog(ERASURE_EXECUTED) entry. The audit entry
    records the subject_ref (a pseudonym), never the name.
    """
    key_row = (
        await session.execute(
            select(SubjectKey).where(SubjectKey.subject_ref == subject_ref)
        )
    ).scalar_one_or_none()

    if key_row is None:
        return False
    if key_row.erased_at is not None:
        return True  # already erased; idempotent

    # Overwrite before delete so the value cannot be recovered from a
    # not-yet-vacuumed page.
    key_row.wrapped_key = b"\x00" * len(key_row.wrapped_key)
    key_row.wrap_nonce = b"\x00" * len(key_row.wrap_nonce)
    key_row.erased_at = datetime.now(tz=__import__("datetime").timezone.utc)
    await session.flush()
    return True