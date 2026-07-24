"""
The register join — ITS contract fields ↔ live monitoring signals.

Nomenclature is load-bearing here. This produces an "ICT third-party
monitoring evidence pack" that ATTACHES TO an Article 28(3) register. It is
not itself a register until the ITS export in Domain 7 is complete and
validated. See compliance/claims_discipline.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import func, select

from backend.ai_assist.contract_extract import ExtractionUnavailable, extract_contract
from backend.ai_assist.schemas import ContractDraftOut
from backend.deps import DB, CurrentOrg, Writer, write_audit
from backend.schemas import ContractIn, ContractOut, JobOut, RegisterRow, VendorOut
from db.models.alert import Alert
from db.models.audit_log import AuditAction
from db.models.contract import Contract, SubstitutabilityRating
from db.models.export_artifact import ExportFormat, ExportKind
from db.models.score import VendorScore
from db.models.vendor import Vendor
from reporting import artifacts as art
from reporting.changelog import build_changelog

router = APIRouter(prefix="/register", tags=["register"])

# ITS fields that must be present for a register row to count as complete.
ITS_REQUIRED = [
    "contractual_arrangement_ref",
    "provider_lei",
    "provider_legal_name",
    "provider_country",
    "function_identifier",
    "start_date",
    "governing_law_country",
    "data_location_countries",
    "substitutability",
    "exit_plan_exists",
]


@router.get("", response_model=list[RegisterRow])
async def register_rows(session: DB, org: CurrentOrg) -> list[RegisterRow]:
    vendors = list(
        (
            await session.execute(
                select(Vendor).where(Vendor.org_id == org.org_id, Vendor.is_active)
            )
        ).scalars()
    )
    if not vendors:
        return []

    ids = [v.id for v in vendors]
    contracts = {
        c.vendor_id: c
        for c in (
            await session.execute(select(Contract).where(Contract.vendor_id.in_(ids)))
        ).scalars()
    }

    latest = (
        select(VendorScore.vendor_id, func.max(VendorScore.computed_at).label("mx"))
        .where(VendorScore.vendor_id.in_(ids))
        .group_by(VendorScore.vendor_id)
        .subquery()
    )
    scores = {
        s.vendor_id: s
        for s in (
            await session.execute(
                select(VendorScore).join(
                    latest,
                    (VendorScore.vendor_id == latest.c.vendor_id)
                    & (VendorScore.computed_at == latest.c.mx),
                )
            )
        ).scalars()
    }
    alerts = dict(
        (
            await session.execute(
                select(Alert.vendor_id, func.count(Alert.id))
                .where(Alert.vendor_id.in_(ids), Alert.is_open)
                .group_by(Alert.vendor_id)
            )
        ).all()
    )

    out = []
    for v in vendors:
        c = contracts.get(v.id)
        out.append(
            RegisterRow(
                vendor=VendorOut.model_validate(v),
                contract=ContractOut.model_validate(c) if c else None,
                composite=scores[v.id].composite if v.id in scores else None,
                last_capture_at=v.last_capture_at,
                open_alerts=alerts.get(v.id, 0),
                completeness_pct=_completeness(c),
            )
        )
    return out


@router.get("/contract/{vendor_id}", response_model=ContractOut)
async def get_contract(
    vendor_id: uuid.UUID, session: DB, org: CurrentOrg
) -> Contract:
    c = (
        await session.execute(
            select(Contract).where(
                Contract.vendor_id == vendor_id, Contract.org_id == org.org_id
            )
        )
    ).scalar_one_or_none()
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No contract record")
    return c


@router.put("/contract/{vendor_id}", response_model=ContractOut)
async def upsert_contract(
    vendor_id: uuid.UUID, body: ContractIn, session: DB, org: Writer
) -> Contract:
    """
    Manual entry, by design. The value was never in COLLECTING these fields —
    it's in JOINING them to live signals. Nobody else joins them.
    """
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")

    c = (
        await session.execute(select(Contract).where(Contract.vendor_id == vendor_id))
    ).scalar_one_or_none()

    data = body.model_dump()
    if data.get("substitutability"):
        data["substitutability"] = SubstitutabilityRating(data["substitutability"])

    if c is None:
        c = Contract(**data, vendor_id=vendor_id, org_id=org.org_id, register_version=1)
        session.add(c)
    else:
        for k, val in data.items():
            setattr(c, k, val)
        c.register_version += 1
    c.last_reviewed_by = org.actor
    await session.flush()

    await write_audit(
        session,
        org,
        AuditAction.CONTRACT_UPDATED,
        entity_type="contract",
        entity_id=c.id,
        detail={"vendor_id": str(vendor_id), "version": c.register_version},
    )
    return c


@router.post("/export", response_model=JobOut)
async def export_register(
    session: DB,
    org: Writer,
    fmt: str = Query("pdf", pattern="^(pdf|its)$"),
) -> JobOut:
    """
    Export is a JOB, never a blocking request.

    Post-artifact-caching this is fast for unchanged vendors, but the cold
    path still regenerates and must not hold an HTTP connection open.
    """
    from backend.jobs.runner import enqueue

    job_id = await enqueue("export_register", str(org.org_id), fmt)

    await write_audit(
        session,
        org,
        AuditAction.REGISTER_EXPORTED if fmt == "its" else AuditAction.PDF_EXPORTED,
        entity_type="org",
        entity_id=org.org_id,
        detail={"format": fmt, "job_id": job_id},
    )
    return JobOut(
        job_id=job_id,
        status="queued",
        enqueued_at=datetime.now(timezone.utc),
        detail={"format": fmt},
    )


@router.post("/contract/{vendor_id}/extract", response_model=ContractDraftOut)
async def extract_contract_fields(
    vendor_id: uuid.UUID,
    session: DB,
    org: Writer,
    file: UploadFile = File(...),
) -> ContractDraftOut:
    """
    Gemma 4 reads the agreement and drafts the register fields.
    NOTHING IS SAVED. The analyst reviews the draft — every field carries the
    verbatim clause it came from — edits, then confirms through
    PUT /register/contract/{vendor_id}, which is the existing tested path.
    The PDF is discarded after extraction. We do not store customer contracts.
    """
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    if file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Only PDF uploads are accepted"
        )
    payload = await file.read()
    try:
        return await extract_contract(
            session,
            vendor_id=vendor_id,
            org_id=org.org_id,
            pdf_bytes=payload,
            filename=file.filename or "contract.pdf",
        )
    except ExtractionUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Automatic extraction unavailable ({exc}). Enter the fields manually.",
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    finally:
        del payload  # do not retain the document


@router.get("/changelog")
async def register_changelog(session: DB, org: CurrentOrg) -> dict:
    """What changed since the last register export — the living-document view."""
    log = await build_changelog(session, org.org_id)
    return log.as_dict()


@router.get("/exports")
async def list_exports(session: DB, org: CurrentOrg) -> list[dict]:
    rows = await art.list_artifacts(session, org.org_id)
    return [
        {
            "id": str(r.id),
            "kind": r.kind.value,
            "format": r.fmt.value,
            "filename": r.filename,
            "size_bytes": r.size_bytes,
            "generated_at": r.generated_at.isoformat(),
            "generated_by": r.generated_by,
            "chain_head_hash": r.chain_head_hash,
            "content_hash": r.content_hash,
            "superseded": r.superseded,
        }
        for r in rows
    ]


@router.get("/exports/{artifact_id}/download")
async def download_export(
    artifact_id: uuid.UUID, session: DB, org: CurrentOrg
) -> Response:
    """
    RETRIEVAL, never regeneration.
    An auditor asking for the March register gets the bytes issued in March.
    Re-rendering would produce a different document and break the trail this
    system exists to provide.
    """
    found = await art.retrieve(session, org.org_id, artifact_id)
    if found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Export not found")
    row, payload = found
    media = {
        "pdf": "application/pdf",
        "its_csv": "application/zip",
        "its_json": "application/json",
    }[row.fmt.value]
    return Response(
        content=payload,
        media_type=media,
        headers={
            "Content-Disposition": f'attachment; filename="{row.filename}"',
            "X-Troy-Content-Hash": row.content_hash,
            "X-Troy-Chain-Head": row.chain_head_hash,
        },
    )


def _completeness(c: Contract | None) -> float:
    if c is None:
        return 0.0
    present = 0
    for f in ITS_REQUIRED:
        v = getattr(c, f, None)
        if v not in (None, "", [], False) or (f == "exit_plan_exists" and v is not None):
            present += 1
    return round(100 * present / len(ITS_REQUIRED), 1)