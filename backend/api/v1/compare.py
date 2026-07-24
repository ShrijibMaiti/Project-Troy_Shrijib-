"""
Multi-vendor comparison.

The natural surface for concentration risk — the question DORA actually cares
about. Cheap to build, immediately useful.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.deps import DB, CurrentOrg
from backend.schemas import CompareCell, CompareOut, ScorePoint, VendorOut
from db.models.score import VendorScore
from db.models.vendor import Vendor

router = APIRouter(prefix="/compare", tags=["compare"])

MAX_VENDORS = 8


@router.get("", response_model=CompareOut)
async def compare(
    session: DB,
    org: CurrentOrg,
    vendor_ids: list[uuid.UUID] = Query(...),
    days: int = Query(180, le=730),
) -> CompareOut:
    if len(vendor_ids) > MAX_VENDORS:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Compare at most {MAX_VENDORS} vendors"
        )

    vendors = list(
        (
            await session.execute(
                select(Vendor).where(
                    Vendor.id.in_(vendor_ids), Vendor.org_id == org.org_id
                )
            )
        ).scalars()
    )
    if len(vendors) != len(set(vendor_ids)):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more vendors not found")

    ids = [v.id for v in vendors]

    latest = (
        select(VendorScore.vendor_id, func.max(VendorScore.computed_at).label("mx"))
        .where(VendorScore.vendor_id.in_(ids))
        .group_by(VendorScore.vendor_id)
        .subquery()
    )
    scores = list(
        (
            await session.execute(
                select(VendorScore)
                .options(selectinload(VendorScore.dimensions))
                .join(
                    latest,
                    (VendorScore.vendor_id == latest.c.vendor_id)
                    & (VendorScore.computed_at == latest.c.mx),
                )
            )
        ).scalars()
    )

    dims: list[str] = []
    matrix: list[CompareCell] = []
    for s in scores:
        for d in s.dimensions:
            name = d.dimension.value if hasattr(d.dimension, "value") else str(d.dimension)
            if name not in dims:
                dims.append(name)
            matrix.append(
                CompareCell(
                    vendor_id=s.vendor_id,
                    dimension=name,
                    z_score=d.z_score,
                    contribution=d.contribution,
                )
            )

    since = datetime.now(timezone.utc) - timedelta(days=days)
    trends: dict[str, list[ScorePoint]] = {}
    for vid in ids:
        rows = (
            await session.execute(
                select(VendorScore.computed_at, VendorScore.composite)
                .where(VendorScore.vendor_id == vid, VendorScore.computed_at >= since)
                .order_by(VendorScore.computed_at.asc())
            )
        ).all()
        trends[str(vid)] = [ScorePoint(computed_at=r[0], composite=r[1]) for r in rows]

    return CompareOut(
        vendors=[VendorOut.model_validate(v) for v in vendors],
        dimensions=dims,
        matrix=matrix,
        trends=trends,
    )