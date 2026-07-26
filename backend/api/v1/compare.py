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
from backend.schemas import (
    CompareCell, CompareOut, ConcentrationCell, ConcentrationFinding,
    ConcentrationOut, ConcentrationRow, ScorePoint, VendorOut,
)
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


@router.get("/concentration", response_model=ConcentrationOut)
async def concentration(session: DB, org: CurrentOrg) -> ConcentrationOut:
    """
    Concentration risk, computed from the register.

    THE POINT OF THE JOIN: a shared fourth party appears in no single vendor's
    own register. Only by joining contracts across the fleet does "two of your
    vendors both subcontract identity checks to the same provider" become
    visible. That is the DORA question this product exists to answer.

    Vendors with no contract record are shown but contribute nothing to the
    findings — they are monitored, not registered, and the note says so.
    """
    from collections import Counter

    from db.models.contract import Contract

    vendors = list(
        (
            await session.execute(
                select(Vendor)
                .where(Vendor.org_id == org.org_id, Vendor.is_active)
                .order_by(Vendor.display_name)
            )
        ).scalars()
    )
    ids = [v.id for v in vendors]

    contracts: dict[uuid.UUID, Contract] = {}
    if ids:
        contracts = {
            c.vendor_id: c
            for c in (
                await session.execute(
                    select(Contract).where(Contract.vendor_id.in_(ids))
                )
            ).scalars()
        }

    scores: dict[uuid.UUID, float] = {}
    if ids:
        latest = (
            select(VendorScore.vendor_id, func.max(VendorScore.computed_at).label("mx"))
            .where(VendorScore.vendor_id.in_(ids))
            .group_by(VendorScore.vendor_id)
            .subquery()
        )
        for s in (
            await session.execute(
                select(VendorScore).join(
                    latest,
                    (VendorScore.vendor_id == latest.c.vendor_id)
                    & (VendorScore.computed_at == latest.c.mx),
                )
            )
        ).scalars():
            scores[s.vendor_id] = s.composite

    def cloud_of(c: Contract | None) -> str:
        """First-ranked subcontractor is treated as the hosting dependency."""
        if not c or not c.subcontractors:
            return "—"
        ranked = sorted(c.subcontractors, key=lambda s: s.get("rank", 99))
        return str(ranked[0].get("name", "—")).upper()

    def region_of(c: Contract | None) -> str:
        if not c or not c.data_location_countries:
            return "—"
        return " · ".join(c.data_location_countries[:2])

    def kyc_of(c: Contract | None) -> str:
        """Any subcontractor beyond rank 1 — the fourth-party tier."""
        if not c or not c.subcontractors:
            return "—"
        rest = [s for s in c.subcontractors if s.get("rank", 1) > 1]
        return str(rest[0].get("name", "—")).upper() if rest else "—"

    def sector_of(c: Contract | None) -> str:
        return (c.ict_service_type or "—").upper() if c else "—"

    raw = {
        v.id: {
            "cloud": cloud_of(contracts.get(v.id)),
            "region": region_of(contracts.get(v.id)),
            "kyc": kyc_of(contracts.get(v.id)),
            "sector": sector_of(contracts.get(v.id)),
        }
        for v in vendors
    }

    counts = {
        col: Counter(r[col] for r in raw.values() if r[col] != "—")
        for col in ("cloud", "region", "kyc", "sector")
    }

    def level(col: str, value: str) -> int:
        if value == "—":
            return 0
        n = counts[col][value]
        return 2 if n >= 3 else 1 if n == 2 else 0

    rows = [
        ConcentrationRow(
            vendor_id=v.id,
            name=v.display_name,
            score=scores.get(v.id),
            cloud=ConcentrationCell(value=raw[v.id]["cloud"], level=level("cloud", raw[v.id]["cloud"])),
            region=ConcentrationCell(value=raw[v.id]["region"], level=level("region", raw[v.id]["region"])),
            kyc=ConcentrationCell(value=raw[v.id]["kyc"], level=level("kyc", raw[v.id]["kyc"])),
            sector=ConcentrationCell(value=raw[v.id]["sector"], level=level("sector", raw[v.id]["sector"])),
            has_contract=v.id in contracts,
        )
        for v in vendors
    ]

    # --- findings, computed not written ------------------------------------
    total = len(vendors)
    findings: list[ConcentrationFinding] = []

    for col, label, why in (
        ("cloud", "SHARE A HOSTING PROVIDER", "A single provider incident correlates these exposures simultaneously."),
        ("kyc", "SHARE A FOURTH-PARTY SUB-PROCESSOR", "This dependency appears in no single vendor's own register — only the join surfaces it."),
        ("region", "CONCENTRATED IN ONE DATA REGION", "A region-level regulatory or infrastructural event touches all of them at once."),
    ):
        if not counts[col]:
            continue
        value, n = counts[col].most_common(1)[0]
        if n < 2:
            continue
        names = [r.name for r in rows if getattr(r, col).value == value]
        elevated = [r.name for r in rows if getattr(r, col).value == value and (r.score or 0) >= 40]
        body = f"{', '.join(names)} on {value}. {why}"
        if elevated:
            body += f" {', '.join(elevated)} {'is' if len(elevated) == 1 else 'are'} already elevated."
        findings.append(
            ConcentrationFinding(
                stat=f"{n} / {total}",
                tone="red" if col == "kyc" else "amber",
                label=f"{label} — {value}",
                body=body,
            )
        )

    with_contract = len(contracts)
    if not findings:
        note = (
            f"No shared dependencies found across {with_contract} registered "
            f"vendor(s). Concentration analysis requires contract records; "
            f"{total - with_contract} of {total} monitored vendors have none."
        )
    else:
        note = (
            f"Computed from {with_contract} contract record(s) across {total} "
            f"monitored vendors. Vendors without a contract record contribute "
            f"nothing to these findings."
        )

    return ConcentrationOut(
        rows=rows,
        findings=findings,
        vendors_total=total,
        vendors_with_contract=with_contract,
        note=note,
    )