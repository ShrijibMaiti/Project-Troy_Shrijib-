"""
Standalone chain verification.

Used by the restore drill and as a demo command: "here is a database whose
owner cannot alter the evidence, and if they do, this reports exactly which
row and why."

Run:  python scripts/verify_chain_cli.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from db.integrity.hash_chain import verify_chain
from db.session import SessionFactory, dispose_engine


async def main() -> int:
    async with SessionFactory() as session:
        result = await verify_chain(session)
    await dispose_engine()

    print(json.dumps(result.as_dict(), indent=2))
    if result.ok:
        print(
            f"\nCHAIN VERIFIED — {result.checked} rows, head {result.head_hash[:16]}…"
        )
        return 0
    print(f"\nCHAIN BROKEN at chain_seq={result.first_break_seq}: {result.reason}")
    return 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
