"""
COST PER VENDOR PER DAY — the number that resolves pricing "TBD".

The original couldn't answer "what does this cost to run", which is exactly
why its pricing said TBD. This aggregates api_cost_events into the figure that
determines whether the product can be priced beneath the enterprise GRC tools
it sits under.

Wrik's ai/cost_meter.py and capture layer write the events; this reads them.

Run:  python infra/observability/cost_dashboard.py --days 30
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from db.models.api_key import ApiCostEvent
from db.models.vendor import Vendor
from db.session import SessionFactory

# The threshold that decides positioning. If cost-per-vendor-per-month lands
# above this, the sub-enterprise pricing story collapses and we need to know
# early, not after a pricing page ships.
VIABILITY_CEILING_USD_PER_VENDOR_MONTH = 15.0


@dataclass
class VendorCost:
    vendor_id: uuid.UUID | None
    display_name: str
    total_usd: float
    per_day_usd: float
    per_month_usd: float
    events: int
    by_provider: dict[str, float] = field(default_factory=dict)


@dataclass
class CostReport:
    window_days: int
    total_usd: float
    active_vendors: int
    mean_per_vendor_month: float
    within_ceiling: bool
    by_provider: dict[str, float]
    by_vendor: list[VendorCost]

    def as_dict(self) -> dict:
        return {
            "window_days": self.window_days,
            "total_usd": round(self.total_usd, 4),
            "active_vendors": self.active_vendors,
            "mean_per_vendor_month_usd": round(self.mean_per_vendor_month, 4),
            "viability_ceiling_usd": VIABILITY_CEILING_USD_PER_VENDOR_MONTH,
            "within_ceiling": self.within_ceiling,
            "by_provider": {k: round(v, 4) for k, v in self.by_provider.items()},
            "by_vendor": [
                {
                    "vendor": v.display_name,
                    "total_usd": round(v.total_usd, 4),
                    "per_month_usd": round(v.per_month_usd, 4),
                    "events": v.events,
                    "by_provider": {k: round(x, 4) for k, x in v.by_provider.items()},
                }
                for v in self.by_vendor
            ],
        }


async def build_report(days: int = 30, org_id: uuid.UUID | None = None) -> CostReport:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    async with SessionFactory() as session:
        base = select(ApiCostEvent).where(ApiCostEvent.created_at >= since)
        if org_id:
            base = base.where(ApiCostEvent.org_id == org_id)

        prov_rows = (
            await session.execute(
                select(ApiCostEvent.provider, func.sum(ApiCostEvent.cost_usd))
                .where(ApiCostEvent.created_at >= since)
                .group_by(ApiCostEvent.provider)
            )
        ).all()
        by_provider = {p: float(c or 0) for p, c in prov_rows}
        total = sum(by_provider.values())

        vend_rows = (
            await session.execute(
                select(
                    ApiCostEvent.vendor_id,
                    ApiCostEvent.provider,
                    func.sum(ApiCostEvent.cost_usd),
                    func.count(ApiCostEvent.id),
                )
                .where(ApiCostEvent.created_at >= since)
                .group_by(ApiCostEvent.vendor_id, ApiCostEvent.provider)
            )
        ).all()

        names = dict(
            (
                await session.execute(select(Vendor.id, Vendor.display_name))
            ).all()
        )
        active = (
            await session.execute(
                select(func.count(Vendor.id)).where(Vendor.is_active, Vendor.capture_enabled)
            )
        ).scalar_one() or 0

    agg: dict[uuid.UUID | None, VendorCost] = {}
    for vid, provider, cost, n in vend_rows:
        cost = float(cost or 0)
        if vid not in agg:
            agg[vid] = VendorCost(
                vendor_id=vid,
                display_name=names.get(vid, "(unattributed)"),
                total_usd=0.0,
                per_day_usd=0.0,
                per_month_usd=0.0,
                events=0,
            )
        vc = agg[vid]
        vc.total_usd += cost
        vc.events += int(n)
        vc.by_provider[provider] = vc.by_provider.get(provider, 0.0) + cost

    for vc in agg.values():
        vc.per_day_usd = vc.total_usd / max(days, 1)
        vc.per_month_usd = vc.per_day_usd * 30

    by_vendor = sorted(agg.values(), key=lambda v: -v.total_usd)
    mean_month = (total / max(active, 1)) / max(days, 1) * 30

    return CostReport(
        window_days=days,
        total_usd=total,
        active_vendors=active,
        mean_per_vendor_month=mean_month,
        within_ceiling=mean_month <= VIABILITY_CEILING_USD_PER_VENDOR_MONTH,
        by_provider=by_provider,
        by_vendor=by_vendor,
    )


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    p = argparse.ArgumentParser(description="Cost per vendor per day")
    p.add_argument("--days", type=int, default=30)
    a = p.parse_args()

    rep = asyncio.run(build_report(days=a.days))
    print(json.dumps(rep.as_dict(), indent=2))

    if rep.total_usd == 0:
        print(
            "\nNo cost events recorded. Wrik's ai/cost_meter.py and capture "
            "layer must write to api_cost_events for this to mean anything."
        )
    elif not rep.within_ceiling:
        print(
            f"\nWARNING: ${rep.mean_per_vendor_month:.2f}/vendor/month exceeds the "
            f"${VIABILITY_CEILING_USD_PER_VENDOR_MONTH:.2f} viability ceiling. "
            "Sub-enterprise pricing may not work at this cost."
        )