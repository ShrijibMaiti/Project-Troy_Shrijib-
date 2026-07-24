"""
Score retrieval with full decomposition.

Never returns a bare composite. Every dimension exposes raw_value, baseline
and z_score separately so the UI can render "why", not just "what" — the fix
for the black-box criticism.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from backend.deps import DB, CurrentOrg
from backend.schemas import ScoreOut, ScorePoint
from db.models.score import VendorScore
from db.models.vendor import Vendor

router = APIRouter(prefix="/scores", tags=["scores"])


@router.get("/vendor/{vendor_id}", response_model=ScoreOut)
async def current_score(
    vendor_id: uuid.UUID, session: DB, org: CurrentOrg
) -> VendorScore:
    await _assert_owned(session, org, vendor_id)
    s = (
        await session.execute(
            select(VendorScore)
            .options(selectinload(VendorScore.dimensions))
            .where(VendorScore.vendor_id == vendor_id)
            .order_by(VendorScore.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if s is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "No score yet — this vendor has not been captured and scored.",
        )
    return s


@router.get("/vendor/{vendor_id}/history", response_model=list[ScorePoint])
async def score_history(
    vendor_id: uuid.UUID,
    session: DB,
    org: CurrentOrg,
    days: int = Query(180, le=1095),
) -> list[ScorePoint]:
    """Trend line for the seismograph. Event markers come from /alerts."""
    await _assert_owned(session, org, vendor_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        await session.execute(
            select(VendorScore.computed_at, VendorScore.composite)
            .where(
                VendorScore.vendor_id == vendor_id,
                VendorScore.computed_at >= since,
            )
            .order_by(VendorScore.computed_at.asc())
        )
    ).all()
    return [ScorePoint(computed_at=r[0], composite=r[1]) for r in rows]


@router.get("/vendor/{vendor_id}/at", response_model=ScoreOut)
async def score_as_of(
    vendor_id: uuid.UUID,
    at: datetime,
    session: DB,
    org: CurrentOrg,
) -> VendorScore:
    """
    Point-in-time retrieval. An auditor asking "what did this say in March"
    gets the score as it stood, including which weights_version produced it.
    """
    await _assert_owned(session, org, vendor_id)
    s = (
        await session.execute(
            select(VendorScore)
            .options(selectinload(VendorScore.dimensions))
            .where(VendorScore.vendor_id == vendor_id, VendorScore.computed_at <= at)
            .order_by(VendorScore.computed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No score at or before that time")
    return s


async def _assert_owned(session, org, vendor_id: uuid.UUID) -> None:
    ok = (
        await session.execute(
            select(Vendor.id).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if ok is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")