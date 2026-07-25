"""Create one org for local/demo use, print its id."""
from __future__ import annotations
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()
from sqlalchemy import select
from db.models.org import Org
from db.session import SessionFactory, dispose_engine

async def main() -> int:
    async with SessionFactory() as s:
        existing = (await s.execute(select(Org).limit(1))).scalar_one_or_none()
        if existing:
            print(f"ORG_ID={existing.id}")
            await dispose_engine(); return 0
        org = Org(
            clerk_org_id="demo-org",
            name="Meridian GRC",
            home_country="IE",
            lei="G5GSEF7VJP5I7OUK5573",       # filer LEI, valid checksum
            entity_type="credit_institution",
        )
        s.add(org); await s.commit()
        print(f"ORG_ID={org.id}")
    await dispose_engine(); return 0

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))