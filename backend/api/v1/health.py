"""
Liveness and per-vendor capture freshness.

We instrument our OWN staleness because staleness is the problem we sell
against. Hiding it while selling against it would be incoherent.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select, text

from backend.config import settings
from backend.deps import DB, CurrentOrg
from backend.schemas import HealthOut, VendorFreshness
from db.cache import healthcheck as redis_ok
from db.models.vendor import Vendor

router = APIRouter(tags=["health"])

STALE_AFTER_DAYS = 3
VERSION = "0.1.0"


@router.get("/health", response_model=HealthOut)
async def health(session: DB) -> HealthOut:
    """Unauthenticated. Used by Railway/Fly healthchecks."""
    db_ok = True
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    r_ok = await redis_ok()

    warnings: list[str] = []
    try:
        warnings = settings.validate_runtime()
    except RuntimeError as exc:
        warnings = [str(exc)]

    calibrated = bool(
        settings.load_calibration("weights") and settings.load_calibration("thresholds")
    )

    if not db_ok:
        st = "error"
    elif not r_ok or warnings:
        st = "degraded"
    else:
        st = "ok"

    return HealthOut(
        status=st,
        environment=settings.environment,
        database=db_ok,
        redis=r_ok,
        calibration=calibrated,
        warnings=warnings,
        version=VERSION,
    )


@router.get("/health/freshness", response_model=list[VendorFreshness])
async def freshness(session: DB, org: CurrentOrg) -> list[VendorFreshness]:
    vendors = list(
        (
            await session.execute(
                select(Vendor).where(Vendor.org_id == org.org_id, Vendor.is_active)
            )
        ).scalars()
    )
    now = datetime.now(timezone.utc)
    out = []
    for v in vendors:
        days = (now - v.last_capture_at).days if v.last_capture_at else None
        out.append(
            VendorFreshness(
                vendor_id=v.id,
                display_name=v.display_name,
                last_capture_at=v.last_capture_at,
                last_capture_ok=v.last_capture_ok,
                stale_days=days,
                is_stale=days is None or days >= STALE_AFTER_DAYS,
            )
        )
    out.sort(key=lambda x: -(x.stale_days or 9999))
    return out
