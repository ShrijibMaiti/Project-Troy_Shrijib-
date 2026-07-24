"""
The Evidence screen's API. This is the moat surface.

Three things no competitor exposes:
  1. TWO audit numbers — narrative resolution AND extraction fidelity.
     Reported separately, never merged.
  2. Live hash-chain verification with the head hash.
  3. The write audit log.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from backend.deps import DB, CurrentOrg, write_audit
from backend.schemas import AuditLogOut, AuditMetricsOut, ChainVerifyOut
from db.cache import VERIFY_TTL, cache_get, cache_set, chain_verify_key
from db.integrity.hash_chain import head_hash_for_export, verify_chain
from db.models.artifact import NarrativeArtifact
from db.models.audit_log import AuditAction, AuditLog
from db.models.vendor import Vendor

router = APIRouter(prefix="/trust", tags=["trust"])


@router.get("/chain-verify", response_model=ChainVerifyOut)
async def chain_verify(
    session: DB,
    org: CurrentOrg,
    force: bool = False,
) -> ChainVerifyOut:
    """
    Walk the chain and recompute every hash.

    Cached briefly — a full walk is O(n) and this endpoint is polled by the
    Evidence screen. `force=true` bypasses the cache for a live demo.
    """
    key = chain_verify_key()
    if not force:
        cached = await cache_get(key)
        if cached:
            return ChainVerifyOut(**cached)

    result = await verify_chain(session)
    out = ChainVerifyOut(
        **result.as_dict(), verified_at=datetime.now(timezone.utc)
    )
    await cache_set(key, out.model_dump(mode="json"), ttl=VERIFY_TTL)

    await write_audit(
        session,
        org,
        AuditAction.CHAIN_VERIFIED,
        detail={"ok": out.ok, "checked": out.checked, "head": out.head_hash[:16]},
    )
    return out


@router.get("/head-hash")
async def head_hash(session: DB, org: CurrentOrg) -> dict:
    """
    The current chain head. Printed on every export so a third party holding
    an old export can detect retroactive tampering without DB access.
    """
    h = await head_hash_for_export(session)
    return {"head_hash": h, "as_of": datetime.now(timezone.utc).isoformat()}


@router.get("/audit-metrics", response_model=AuditMetricsOut)
async def audit_metrics(
    session: DB,
    org: CurrentOrg,
    vendor_id: uuid.UUID | None = None,
) -> AuditMetricsOut:
    """
    Two numbers, never one.

    narrative_resolution_pct — every citation marker resolves to a signal.
    extraction_fidelity_pct  — the stored excerpt actually supports the claim.

    The second is the layer the original never had, and it's where
    hallucination actually enters. Counting is on DISTINCT claims and DISTINCT
    citations, not marker occurrences — the original conflated the two and
    overstated itself.
    """
    stmt = (
        select(
            func.avg(NarrativeArtifact.citation_resolution_pct),
            func.sum(NarrativeArtifact.distinct_claims),
            func.sum(NarrativeArtifact.distinct_citations),
            func.sum(NarrativeArtifact.unresolved_count),
            func.avg(NarrativeArtifact.entailment_fidelity_pct),
            func.sum(NarrativeArtifact.entailment_sampled),
            func.sum(NarrativeArtifact.entailment_failed),
            func.count(NarrativeArtifact.id),
        )
        .join(Vendor, Vendor.id == NarrativeArtifact.vendor_id)
        .where(Vendor.org_id == org.org_id)
    )
    if vendor_id:
        stmt = stmt.where(NarrativeArtifact.vendor_id == vendor_id)

    r = (await session.execute(stmt)).first()
    return AuditMetricsOut(
        narrative_resolution_pct=round(r[0], 2) if r[0] is not None else None,
        distinct_claims=int(r[1] or 0),
        distinct_citations=int(r[2] or 0),
        unresolved_count=int(r[3] or 0),
        extraction_fidelity_pct=round(r[4], 2) if r[4] is not None else None,
        entailment_sampled=int(r[5] or 0),
        entailment_failed=int(r[6] or 0),
        artifacts_counted=int(r[7] or 0),
    )


@router.get("/audit-log", response_model=list[AuditLogOut])
async def audit_log(
    session: DB,
    org: CurrentOrg,
    days: int = Query(90, le=730),
    action: str | None = None,
    limit: int = Query(200, le=1000),
) -> list[AuditLog]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(AuditLog)
        .where(AuditLog.org_id == org.org_id, AuditLog.created_at >= since)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
    )
    if action:
        try:
            stmt = stmt.where(AuditLog.action == AuditAction(action))
        except ValueError:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown action '{action}'")
    return list((await session.execute(stmt)).scalars())


@router.get("/model-versions")
async def model_versions(session: DB, org: CurrentOrg) -> dict:
    """Which model and prompt produced the artifacts currently in use."""
    rows = (
        await session.execute(
            select(
                NarrativeArtifact.model_id,
                NarrativeArtifact.prompt_name,
                NarrativeArtifact.prompt_hash,
                func.count(NarrativeArtifact.id),
                func.max(NarrativeArtifact.generated_at),
            )
            .join(Vendor, Vendor.id == NarrativeArtifact.vendor_id)
            .where(Vendor.org_id == org.org_id)
            .group_by(
                NarrativeArtifact.model_id,
                NarrativeArtifact.prompt_name,
                NarrativeArtifact.prompt_hash,
            )
        )
    ).all()
    return {
        "versions": [
            {
                "model_id": m,
                "prompt_name": pn,
                "prompt_hash": ph,
                "artifact_count": n,
                "latest": ts.isoformat() if ts else None,
            }
            for m, pn, ph, n, ts in rows
        ]
    }