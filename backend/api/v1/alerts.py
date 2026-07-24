"""
Convergence alerts + threshold preview.

The preview endpoint is the anti-alert-fatigue tool: before committing to a
threshold, replay history and see how often it WOULD have fired. Turns the
alert budget from a principle into a number.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from backend.config import settings
from backend.deps import DB, CurrentOrg, Writer, write_audit
from backend.schemas import AlertOut, ThresholdPreviewOut
from db.models.alert import Alert
from db.models.audit_log import AuditAction
from db.models.vendor import Vendor

router = APIRouter(prefix="/alerts", tags=["alerts"])

ALERT_BUDGET_PER_VENDOR_PER_QUARTER = 1.0


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    session: DB,
    org: CurrentOrg,
    open_only: bool = True,
    days: int = Query(90, le=730),
    limit: int = Query(100, le=500),
) -> list[Alert]:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(Alert)
        .join(Vendor, Vendor.id == Alert.vendor_id)
        .where(Vendor.org_id == org.org_id, Alert.fired_at >= since)
        .order_by(Alert.fired_at.desc())
        .limit(limit)
    )
    if open_only:
        stmt = stmt.where(Alert.is_open)
    return list((await session.execute(stmt)).scalars())


@router.get("/vendor/{vendor_id}", response_model=list[AlertOut])
async def vendor_alerts(
    vendor_id: uuid.UUID, session: DB, org: CurrentOrg
) -> list[Alert]:
    """Also supplies the event markers overlaid on the score trend chart."""
    return list(
        (
            await session.execute(
                select(Alert)
                .join(Vendor, Vendor.id == Alert.vendor_id)
                .where(Alert.vendor_id == vendor_id, Vendor.org_id == org.org_id)
                .order_by(Alert.fired_at.desc())
            )
        ).scalars()
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge(alert_id: uuid.UUID, session: DB, org: Writer) -> Alert:
    """
    Only ack/notify fields may change — enforced by trg_alerts_ack_only.
    The fired facts (severity, dimensions, threshold) are immutable.
    """
    a = (
        await session.execute(
            select(Alert)
            .join(Vendor, Vendor.id == Alert.vendor_id)
            .where(Alert.id == alert_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if a is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert not found")

    a.acknowledged_at = datetime.now(timezone.utc)
    a.acknowledged_by = org.actor
    a.is_open = False

    await write_audit(
        session,
        org,
        AuditAction.ALERT_ACKNOWLEDGED,
        entity_type="alert",
        entity_id=a.id,
    )
    return a


@router.get("/threshold-preview", response_model=ThresholdPreviewOut)
async def threshold_preview(
    session: DB,
    org: CurrentOrg,
    candidate: float = Query(..., ge=0, le=100),
    days: int = Query(365, le=1095),
) -> ThresholdPreviewOut:
    """
    "This setting would have fired N times over the last N days."

    Replays historical convergence_score values against a candidate threshold.
    Note the honest limitation: it replays alerts we ALREADY computed, so it
    cannot show alerts that a lower threshold would have surfaced from scores
    that never generated an Alert row. Genuine sweeps live in Wrik's backtest
    harness; this is the operational approximation.
    """
    since = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        await session.execute(
            select(Alert.convergence_score, Alert.threshold_value)
            .join(Vendor, Vendor.id == Alert.vendor_id)
            .where(Vendor.org_id == org.org_id, Alert.fired_at >= since)
        )
    ).all()

    vendor_count = (
        await session.execute(
            select(func.count(Vendor.id)).where(
                Vendor.org_id == org.org_id, Vendor.is_active
            )
        )
    ).scalar_one() or 1

    would = sum(1 for cs, _ in rows if cs >= candidate)
    current_threshold = rows[0][1] if rows else None
    quarters = max(days / 91.0, 0.01)
    rate = would / vendor_count / quarters

    thresholds = settings.load_calibration("thresholds")
    if current_threshold is None and thresholds:
        current_threshold = thresholds.get("convergence")

    return ThresholdPreviewOut(
        candidate_threshold=candidate,
        current_threshold=current_threshold,
        would_fire=would,
        currently_fires=len(rows),
        window_days=days,
        per_vendor_per_quarter=round(rate, 3),
        within_budget=rate <= ALERT_BUDGET_PER_VENDOR_PER_QUARTER,
        budget=ALERT_BUDGET_PER_VENDOR_PER_QUARTER,
    )