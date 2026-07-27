"""
Retention policy enforcement.

Two distinct clocks, and conflating them is the mistake:

  EVIDENCE (signals, excerpts, artifacts) — retained indefinitely. That is
  the point of the system; a monitoring record that expires cannot support an
  audit two years later.

  PERSONAL IDENTIFIERS inside that evidence — retained only while there is a
  legitimate interest. After the retention window they are crypto-shredded.
  The signal survives ("CFO departed"), the name does not.

Run as a scheduled job. Reports in dry-run mode by default: automatic
destruction of data should require an explicit flag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from db.integrity.crypto_shred import ShreddedField, SubjectKey, erase_subject
from db.models.audit_log import AuditAction, AuditLog
from db.session import SessionFactory

# Personal identifiers are shredded this long after the signal was observed.
# 24 months matches a typical vendor-risk review cycle plus one year.
PII_RETENTION_DAYS = 730


@dataclass
class RetentionReport:
    cutoff: datetime
    subjects_examined: int
    subjects_eligible: int
    subjects_shredded: int
    dry_run: bool

    def as_dict(self) -> dict:
        return {
            "cutoff": self.cutoff.isoformat(),
            "subjects_examined": self.subjects_examined,
            "subjects_eligible": self.subjects_eligible,
            "subjects_shredded": self.subjects_shredded,
            "dry_run": self.dry_run,
        }


async def enforce_retention(
    dry_run: bool = True, retention_days: int = PII_RETENTION_DAYS
) -> RetentionReport:
    """
    Shred identifiers whose newest referencing field is older than the window.

    Eligibility is based on the NEWEST field per subject, not the oldest — an
    executive mentioned again last month is still current, however old the
    first mention was.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)

    async with SessionFactory() as session:
        rows = (
            await session.execute(
                select(
                    ShreddedField.subject_ref,
                    func.max(ShreddedField.created_at).label("newest"),
                ).group_by(ShreddedField.subject_ref)
            )
        ).all()

        examined = len(rows)
        eligible = [ref for ref, newest in rows if newest < cutoff]

        already = set(
            (
                await session.execute(
                    select(SubjectKey.subject_ref).where(
                        SubjectKey.subject_ref.in_(eligible),
                        SubjectKey.erased_at.isnot(None),
                    )
                )
            ).scalars()
            if eligible
            else []
        )
        pending = [r for r in eligible if r not in already]

        shredded = 0
        if not dry_run:
            for ref in pending:
                if await erase_subject(session, ref):
                    shredded += 1

            session.add(
                AuditLog(
                    action=AuditAction.ERASURE_EXECUTED,
                    actor="system:retention",
                    detail={
                        "policy": "pii_retention",
                        "retention_days": retention_days,
                        "shredded": shredded,
                    },
                    note="Automated retention enforcement",
                )
            )
            await session.commit()

    return RetentionReport(
        cutoff=cutoff,
        subjects_examined=examined,
        subjects_eligible=len(pending),
        subjects_shredded=shredded,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    p = argparse.ArgumentParser(description="Enforce PII retention policy")
    p.add_argument(
        "--execute", action="store_true", help="actually shred (default: dry run)"
    )
    p.add_argument("--days", type=int, default=PII_RETENTION_DAYS)
    a = p.parse_args()

    report = asyncio.run(
        enforce_retention(dry_run=not a.execute, retention_days=a.days)
    )
    print(json.dumps(report.as_dict(), indent=2))
