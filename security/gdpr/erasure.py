"""
GDPR Article 17 erasure endpoint.

The mechanism: destroy the subject's data key. Every ciphertext referencing
that key becomes permanently undecryptable. NO SIGNAL ROW IS TOUCHED, so the
hash chain remains valid and verifiable.

This is what lets "we never delete evidence" and "you have a right to
erasure" both be true. The alternative — deleting signal rows — would break
the chain and destroy the audit trail for every OTHER vendor in the sequence.

The request is logged as a tombstone. Proving an erasure was honoured needs a
record that it happened; that record holds only the pseudonymous subject_ref.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.deps import DB, Admin, write_audit
from db.integrity.crypto_shred import ShreddedField, SubjectKey, erase_subject
from db.models.api_key import ErasureRequest, ErasureStatus
from db.models.audit_log import AuditAction

router = APIRouter(prefix="/gdpr", tags=["gdpr"])


class ErasureIn(BaseModel):
    # Either a pseudonymous ref, or the name + vendor to derive one.
    subject_ref: str | None = None
    subject_name: str | None = None
    vendor_id: uuid.UUID | None = None
    note: str | None = None


class ErasureOut(BaseModel):
    request_id: uuid.UUID
    subject_ref: str
    status: str
    fields_affected: int
    executed_at: datetime | None
    chain_intact: bool


def derive_subject_ref(name: str, vendor_id: uuid.UUID) -> str:
    """
    Must match the derivation used at encryption time, or the key won't be
    found and the erasure silently no-ops.
    """
    return hashlib.sha256(f"{name.strip().lower()}|{vendor_id}".encode()).hexdigest()[
        :40
    ]


@router.post("/erasure", response_model=ErasureOut)
async def request_erasure(body: ErasureIn, session: DB, org: Admin) -> ErasureOut:
    if body.subject_ref:
        ref = body.subject_ref
    elif body.subject_name and body.vendor_id:
        ref = derive_subject_ref(body.subject_name, body.vendor_id)
    else:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Provide subject_ref, or subject_name plus vendor_id",
        )

    affected = (
        await session.execute(
            select(func.count(ShreddedField.id)).where(ShreddedField.subject_ref == ref)
        )
    ).scalar_one()

    req = ErasureRequest(
        subject_ref=ref,
        org_id=org.org_id,
        requested_by=org.actor,
        note=body.note,
        fields_affected=affected,
    )
    session.add(req)
    await session.flush()

    await write_audit(
        session,
        org,
        AuditAction.ERASURE_REQUESTED,
        entity_type="subject",
        detail={"subject_ref": ref, "fields": affected},
    )

    done = await erase_subject(session, ref)
    if not done:
        req.status = ErasureStatus.REJECTED
        req.note = (req.note or "") + " [no key found for subject]"
        return ErasureOut(
            request_id=req.id,
            subject_ref=ref,
            status=req.status.value,
            fields_affected=0,
            executed_at=None,
            chain_intact=True,
        )

    req.status = ErasureStatus.EXECUTED
    req.executed_at = datetime.now(timezone.utc)

    await write_audit(
        session,
        org,
        AuditAction.ERASURE_EXECUTED,
        entity_type="subject",
        detail={"subject_ref": ref, "fields": affected},
    )

    # Prove the chain survived. If this ever returns False, the erasure
    # mechanism has a bug and the compliance story is broken.
    from db.integrity.hash_chain import verify_chain

    chain = await verify_chain(session)

    return ErasureOut(
        request_id=req.id,
        subject_ref=ref,
        status=req.status.value,
        fields_affected=affected,
        executed_at=req.executed_at,
        chain_intact=chain.ok,
    )


@router.get("/erasure", response_model=list[ErasureOut])
async def list_erasures(session: DB, org: Admin) -> list[ErasureOut]:
    rows = list(
        (
            await session.execute(
                select(ErasureRequest)
                .where(ErasureRequest.org_id == org.org_id)
                .order_by(ErasureRequest.created_at.desc())
            )
        ).scalars()
    )
    return [
        ErasureOut(
            request_id=r.id,
            subject_ref=r.subject_ref,
            status=r.status.value,
            fields_affected=r.fields_affected or 0,
            executed_at=r.executed_at,
            chain_intact=True,
        )
        for r in rows
    ]


@router.get("/subjects/{subject_ref}/status")
async def subject_status(subject_ref: str, session: DB, org: Admin) -> dict:
    """Article 15 — is this subject's data still held?"""
    key = (
        await session.execute(
            select(SubjectKey).where(SubjectKey.subject_ref == subject_ref)
        )
    ).scalar_one_or_none()
    fields = (
        await session.execute(
            select(func.count(ShreddedField.id)).where(
                ShreddedField.subject_ref == subject_ref
            )
        )
    ).scalar_one()

    return {
        "subject_ref": subject_ref,
        "exists": key is not None,
        "erased": key.erased_at is not None if key else None,
        "erased_at": key.erased_at.isoformat() if key and key.erased_at else None,
        "encrypted_fields": fields,
        "note": (
            "Erasure destroys the decryption key. Ciphertext rows are retained "
            "so the hash chain stays verifiable; the plaintext is unrecoverable."
        ),
    }
