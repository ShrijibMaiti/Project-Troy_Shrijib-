"""
Vendor CRUD — the fix for the hardcoded SYSTEM_DASHBOARD_VENDORS list.

The database is now the ONLY source of truth for what gets monitored. There is
no constant anywhere in this repo naming a vendor.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select

from backend.ai_assist.schemas import VendorProfileDraft
from backend.ai_assist.vendor_profile import ProfileUnavailable, profile_vendor
from backend.deps import DB, Admin, CurrentOrg, Writer, write_audit
from backend.schemas import (
    VendorCreate,
    VendorFleetItem,
    VendorOut,
    VendorUpdate,
)
from db.models.alert import Alert
from db.models.audit_log import AuditAction
from db.models.score import VendorScore
from db.models.vendor import EntityType, Vendor

router = APIRouter(prefix="/vendors", tags=["vendors"])

STALE_AFTER_DAYS = 3


@router.get("", response_model=list[VendorFleetItem])
async def list_vendors(
    session: DB,
    org: CurrentOrg,
    include_inactive: bool = False,
    sort: str = Query("score", pattern="^(score|name|staleness|delta)$"),
) -> list[VendorFleetItem]:
    """Fleet view: vendor + latest score + open alerts + capture freshness."""
    stmt = select(Vendor).where(Vendor.org_id == org.org_id)
    if not include_inactive:
        stmt = stmt.where(Vendor.is_active)
    vendors = list((await session.execute(stmt)).scalars())

    if not vendors:
        return []

    ids = [v.id for v in vendors]

    # Latest score per vendor.
    latest = (
        select(
            VendorScore.vendor_id,
            func.max(VendorScore.computed_at).label("mx"),
        )
        .where(VendorScore.vendor_id.in_(ids))
        .group_by(VendorScore.vendor_id)
        .subquery()
    )
    score_rows = (
        await session.execute(
            select(VendorScore).join(
                latest,
                (VendorScore.vendor_id == latest.c.vendor_id)
                & (VendorScore.computed_at == latest.c.mx),
            )
        )
    ).scalars()
    scores = {s.vendor_id: s for s in score_rows}

    alert_counts = dict(
        (
            await session.execute(
                select(Alert.vendor_id, func.count(Alert.id))
                .where(Alert.vendor_id.in_(ids), Alert.is_open)
                .group_by(Alert.vendor_id)
            )
        ).all()
    )

    now = datetime.now(timezone.utc)
    out: list[VendorFleetItem] = []
    for v in vendors:
        stale_days = None
        if v.last_capture_at:
            stale_days = (now - v.last_capture_at).days
        s = scores.get(v.id)
        out.append(
            VendorFleetItem(
                **VendorOut.model_validate(v).model_dump(),
                composite=s.composite if s else None,
                delta=s.delta if s else None,
                open_alerts=alert_counts.get(v.id, 0),
                stale_days=stale_days,
                is_stale=stale_days is None or stale_days >= STALE_AFTER_DAYS,
            )
        )

    keys = {
        "score": lambda x: -(x.composite or -1),
        "name": lambda x: x.display_name.lower(),
        "staleness": lambda x: -(x.stale_days or 9999),
        "delta": lambda x: -(x.delta or 0),
    }
    out.sort(key=keys[sort])
    return out


class VendorProfileIn(BaseModel):
    name: str


@router.post("/profile", response_model=VendorProfileDraft)
async def draft_vendor_profile(
    body: VendorProfileIn, session: DB, org: Writer
) -> VendorProfileDraft:
    """
    Gemma drafts identifying details and disambiguation terms for a vendor name.
    NOTHING IS CREATED. The analyst reviews the draft, edits it, then submits
    through POST /vendors — the existing, tested creation path.
    """
    try:
        return await profile_vendor(session, name=body.name, org_id=org.org_id)
    except ProfileUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Profiling unavailable ({exc}). Enter the fields manually.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/{vendor_id}", response_model=VendorOut)
async def get_vendor(vendor_id: uuid.UUID, session: DB, org: CurrentOrg) -> Vendor:
    v = await _owned(session, org, vendor_id)
    return v


@router.post("", response_model=VendorOut, status_code=status.HTTP_201_CREATED)
async def create_vendor(body: VendorCreate, session: DB, org: Writer) -> Vendor:
    if body.lei:
        dupe = (
            await session.execute(select(Vendor).where(Vendor.lei == body.lei))
        ).scalar_one_or_none()
        if dupe is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"LEI {body.lei} is already monitored"
            )

    v = Vendor(
        **body.model_dump(exclude={"entity_type"}),
        entity_type=EntityType(body.entity_type),
        org_id=org.org_id,
    )
    session.add(v)
    await session.flush()

    await write_audit(
        session,
        org,
        AuditAction.VENDOR_CREATED,
        entity_type="vendor",
        entity_id=v.id,
        detail={"display_name": v.display_name, "lei": v.lei},
    )
    return v


@router.patch("/{vendor_id}", response_model=VendorOut)
async def update_vendor(
    vendor_id: uuid.UUID, body: VendorUpdate, session: DB, org: Writer
) -> Vendor:
    v = await _owned(session, org, vendor_id)
    changes = body.model_dump(exclude_unset=True)

    if "entity_type" in changes:
        changes["entity_type"] = EntityType(changes["entity_type"])
    for k, val in changes.items():
        setattr(v, k, val)

    await write_audit(
        session,
        org,
        AuditAction.VENDOR_UPDATED,
        entity_type="vendor",
        entity_id=v.id,
        detail={"changed": list(changes)},
    )
    return v


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_vendor(vendor_id: uuid.UUID, session: DB, org: Admin) -> None:
    """
    Deactivate, never delete. Signals are append-only evidence and the vendor
    row is their parent — removing it would orphan the chain.
    """
    v = await _owned(session, org, vendor_id)
    v.is_active = False
    v.capture_enabled = False
    await write_audit(
        session,
        org,
        AuditAction.VENDOR_DEACTIVATED,
        entity_type="vendor",
        entity_id=v.id,
    )


async def _owned(session, org, vendor_id: uuid.UUID) -> Vendor:
    v = (
        await session.execute(
            select(Vendor).where(Vendor.id == vendor_id, Vendor.org_id == org.org_id)
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")
    return v
