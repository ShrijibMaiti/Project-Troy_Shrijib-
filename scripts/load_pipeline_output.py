"""
Load Wrik's pipeline output into Troy for the demo.

  python scripts/load_pipeline_output.py path/to/output.json --org <org_id>

Accepts either a single vendor object or a list of them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import select

from backend.ingest.from_pipeline import ingest_many
from db.models.org import Org
from db.session import SessionFactory, dispose_engine


async def main(path: str, org_id: str | None) -> int:
    data = json.load(open(path, encoding="utf-8"))
    outputs = data if isinstance(data, list) else [data]

    async with SessionFactory() as s:
        if org_id:
            oid = uuid.UUID(org_id)
        else:
            org = (
                await s.execute(select(Org).where(Org.is_active).limit(1))
            ).scalar_one_or_none()
            if org is None:
                print("No org exists. Create one first.")
                return 1
            oid = org.id

        results = await ingest_many(s, oid, outputs)
        await s.commit()

    for r in results:
        print(
            f"  {r['vendor']}: composite {r['composite_0_100']:.1f}/100, "
            f"{r['signals_written']} signals, dims {r['dimensions_scored']}"
        )
    print(f"\nLoaded {len(results)} vendor(s). Chain still intact:")
    await dispose_engine()
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("path")
    p.add_argument("--org", default=None)
    a = p.parse_args()
    raise SystemExit(asyncio.run(main(a.path, a.org)))
