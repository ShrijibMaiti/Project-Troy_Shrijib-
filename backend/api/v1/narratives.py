"""
Immutable narrative artifacts.

THERE IS NO REGENERATE ENDPOINT, DELIBERATELY.

An auditor asking "show me the March report" gets a RETRIEVAL. Re-running a
non-deterministic model would produce a different document and break the very
trail this system exists to provide. Generation happens once, in the job
pipeline, and the result is frozen with its model_id and prompt_hash.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, text

from backend.deps import DB, CurrentOrg
from backend.schemas import CitationOut, NarrativeOut
from db.models.artifact import NarrativeArtifact
from db.models.vendor import Vendor

router = APIRouter(prefix="/narratives", tags=["narratives"])


@router.get("/vendor/{vendor_id}", response_model=NarrativeOut)
async def latest_narrative(
    vendor_id: uuid.UUID, session: DB, org: CurrentOrg
) -> NarrativeArtifact:
    await _assert_owned(session, org, vendor_id)
    a = (
        await session.execute(
            select(NarrativeArtifact)
            .where(NarrativeArtifact.vendor_id == vendor_id)
            .order_by(NarrativeArtifact.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No narrative generated yet")
    return a


@router.get("/vendor/{vendor_id}/at", response_model=NarrativeOut)
async def narrative_as_of(
    vendor_id: uuid.UUID, at: datetime, session: DB, org: CurrentOrg
) -> NarrativeArtifact:
    """Point-in-time retrieval. This is the auditor's endpoint."""
    await _assert_owned(session, org, vendor_id)
    a = (
        await session.execute(
            select(NarrativeArtifact)
            .where(
                NarrativeArtifact.vendor_id == vendor_id,
                NarrativeArtifact.generated_at <= at,
            )
            .order_by(NarrativeArtifact.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No narrative at or before that time")
    return a


@router.get("/vendor/{vendor_id}/history", response_model=list[NarrativeOut])
async def narrative_history(
    vendor_id: uuid.UUID,
    session: DB,
    org: CurrentOrg,
    limit: int = Query(50, le=200),
) -> list[NarrativeArtifact]:
    await _assert_owned(session, org, vendor_id)
    return list(
        (
            await session.execute(
                select(NarrativeArtifact)
                .where(NarrativeArtifact.vendor_id == vendor_id)
                .order_by(NarrativeArtifact.generated_at.desc())
                .limit(limit)
            )
        ).scalars()
    )


@router.get("/{artifact_id}/citations", response_model=list[CitationOut])
async def artifact_citations(
    artifact_id: uuid.UUID, session: DB, org: CurrentOrg
) -> list[CitationOut]:
    """
    Resolved citations for the inline chips: source URL, Wayback archive URL,
    the stored excerpt (hover preview) and the confidence tier.
    """
    a = (
        await session.execute(
            select(NarrativeArtifact)
            .join(Vendor, Vendor.id == NarrativeArtifact.vendor_id)
            .where(NarrativeArtifact.id == artifact_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Artifact not found")

    out: list[CitationOut] = []
    for c in a.citations or []:
        sid = c.get("signal_id")
        excerpt = url = archive = None
        if sid:
            row = (
                await session.execute(
                    text(
                        """
                        SELECT s.source_url, s.archive_url, e.text
                        FROM signals s
                        LEFT JOIN excerpts e ON e.id = s.excerpt_id
                        WHERE s.id = CAST(:sid AS uuid)
                        """
                    ),
                    {"sid": sid},
                )
            ).first()
            if row:
                url, archive, excerpt = row

        out.append(
            CitationOut(
                index=c.get("index", 0),
                signal_id=uuid.UUID(sid) if sid else None,
                url=c.get("url") or url,
                archive_url=c.get("archive_url") or archive,
                excerpt=excerpt,
                confidence=c.get("confidence"),
            )
        )
    return sorted(out, key=lambda x: x.index)


async def _assert_owned(session, org, vendor_id: uuid.UUID) -> None:
    ok = (
        await session.execute(
            select(Vendor.id).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if ok is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")