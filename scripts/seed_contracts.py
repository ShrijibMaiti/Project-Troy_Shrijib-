"""
Seed representative contract records for the demo vendors.

These are ANALYST-ENTERED values, which is how contract data enters Troy by
design — Troy monitors public signals, it does not scrape private agreements.
The concentration findings computed from them are real joins over real rows;
the inputs are illustrative.
"""
from __future__ import annotations

import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from datetime import date
from sqlalchemy import select
from db.models.contract import Contract, SubstitutabilityRating
from db.models.vendor import Vendor
from db.session import SessionFactory, dispose_engine

SEED = {
    "Silicon Valley Bank": dict(
        ref="CA-SVB-001", country="US", fn_id="F-BANK-01", fn="Deposit & treasury services",
        svc="banking infrastructure", law="US",
        data=["US", "IE"], proc=["US"],
        subs=[{"name": "AWS", "rank": 1, "country": "US"},
              {"name": "Verapoint", "rank": 2, "country": "IE"}],
        subst=SubstitutabilityRating.NOT_SUBSTITUTABLE, exit_plan=False, cost=1_200_000,
    ),
    "Stripe": dict(
        ref="CA-STR-002", country="US", fn_id="F-PAY-01", fn="Payment processing",
        svc="payment infrastructure", law="US",
        data=["US", "IE"], proc=["US"],
        subs=[{"name": "AWS", "rank": 1, "country": "US"},
              {"name": "Verapoint", "rank": 2, "country": "IE"}],
        subst=SubstitutabilityRating.HIGHLY_COMPLEX, exit_plan=True, cost=450_000,
    ),
    "Fifth Third Bancorp": dict(
        ref="CA-FTB-003", country="US", fn_id="F-BANK-02", fn="Correspondent banking",
        svc="banking infrastructure", law="US",
        data=["US"], proc=["US"],
        subs=[{"name": "Azure", "rank": 1, "country": "US"}],
        subst=SubstitutabilityRating.MEDIUM_COMPLEX, exit_plan=True, cost=300_000,
    ),
}


async def main() -> int:
    async with SessionFactory() as s:
        made = 0
        for name, cfg in SEED.items():
            v = (await s.execute(
                select(Vendor).where(Vendor.display_name == name)
            )).scalar_one_or_none()
            if v is None:
                print(f"  skip {name} — vendor not found")
                continue
            existing = (await s.execute(
                select(Contract).where(Contract.vendor_id == v.id)
            )).scalar_one_or_none()
            if existing:
                print(f"  skip {name} — contract exists")
                continue
            s.add(Contract(
                vendor_id=v.id, org_id=v.org_id,
                contractual_arrangement_ref=cfg["ref"],
                provider_legal_name=v.legal_name,
                provider_country=cfg["country"],
                function_identifier=cfg["fn_id"], function_name=cfg["fn"],
                ict_service_type=cfg["svc"],
                supports_critical_function=True,
                start_date=date(2024, 1, 1), end_date=date(2027, 1, 1),
                notice_period_days=90, governing_law_country=cfg["law"],
                annual_cost_eur=cfg["cost"],
                data_location_countries=cfg["data"],
                processing_location_countries=cfg["proc"],
                sensitive_data_involved=True,
                subcontractors=cfg["subs"],
                substitutability=cfg["subst"],
                exit_plan_exists=cfg["exit_plan"],
                reintegration_possible=cfg["exit_plan"],
                last_reviewed_by="demo-seed",
            ))
            made += 1
            print(f"  + {name}")
        await s.commit()
        print(f"\n{made} contract(s) created.")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))