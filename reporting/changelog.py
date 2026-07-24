"""
Register version diffing — the "living document" mechanic.

A register is not a snapshot; it changes as contracts are signed, amended and
terminated. This tracks what changed between register versions so the export
can answer "what moved since the last submission" rather than forcing a
line-by-line comparison of two PDFs.

Built on `contracts.register_version`, which increments on every confirmed
edit, and on the append-only export artifact history.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.audit_log import AuditAction, AuditLog
from db.models.contract import Contract
from db.models.export_artifact import ExportArtifact, ExportKind
from db.models.vendor import Vendor

TRACKED_FIELDS = [
    "contractual_arrangement_ref", "provider_lei", "provider_country",
    "function_identifier", "ict_service_type", "supports_critical_function",
    "start_date", "end_date", "notice_period_days", "governing_law_country",
    "annual_cost_eur", "data_location_countries", "processing_location_countries",
    "sensitive_data_involved", "subcontractors", "substitutability",
    "exit_plan_exists", "exit_plan_last_tested", "reintegration_possible",
]


@dataclass
class ChangeEntry:
    vendor_name: str
    vendor_id: uuid.UUID
    change_type: str          # added | amended | removed
    register_version: int
    changed_at: datetime
    changed_by: str
    fields_changed: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "vendor": self.vendor_name,
            "vendor_id": str(self.vendor_id),
            "change_type": self.change_type,
            "register_version": self.register_version,
            "changed_at": self.changed_at.isoformat(),
            "changed_by": self.changed_by,
            "fields_changed": self.fields_changed,
        }


@dataclass
class RegisterChangelog:
    since: datetime | None
    until: datetime
    entries: list[ChangeEntry]
    previous_export: dict | None
    current_version: int

    def as_dict(self) -> dict:
        return {
            "since": self.since.isoformat() if self.since else None,
            "until": self.until.isoformat(),
            "current_register_version": self.current_version,
            "previous_export": self.previous_export,
            "change_count": len(self.entries),
            "changes": [e.as_dict() for e in self.entries],
        }


async def build_changelog(
    session: AsyncSession, org_id: uuid.UUID, since: datetime | None = None
) -> RegisterChangelog:
    """
    Changes since a given time, or since the last ITS export if not specified.

    Defaulting to "since the last export" is the useful behaviour: the question
    a register owner actually asks is "what changed since I last filed."
    """
    prev_export = None
    if since is None:
        last = (
            await session.execute(
                select(ExportArtifact)
                .where(
                    ExportArtifact.org_id == org_id,
                    ExportArtifact.kind == ExportKind.ITS_REGISTER,
                )
                .order_by(ExportArtifact.generated_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last:
            since = last.generated_at
            prev_export = {
                "artifact_id": str(last.id),
                "generated_at": last.generated_at.isoformat(),
                "content_hash": last.content_hash,
                "chain_head_hash": last.chain_head_hash,
            }

    stmt = (
        select(AuditLog)
        .where(
            AuditLog.org_id == org_id,
            AuditLog.action == AuditAction.CONTRACT_UPDATED,
        )
        .order_by(AuditLog.created_at.asc())
    )
    if since:
        stmt = stmt.where(AuditLog.created_at > since)

    logs = list((await session.execute(stmt)).scalars())

    vendor_names = dict(
        (
            await session.execute(
                select(Vendor.id, Vendor.display_name).where(Vendor.org_id == org_id)
            )
        ).all()
    )

    contracts = {
        c.id: c
        for c in (
            await session.execute(select(Contract).where(Contract.org_id == org_id))
        ).scalars()
    }

    entries: list[ChangeEntry] = []
    for lg in logs:
        c = contracts.get(lg.entity_id)
        vid = c.vendor_id if c else uuid.UUID(lg.detail.get("vendor_id", str(uuid.uuid4())))
        version = int(lg.detail.get("version", 0))
        entries.append(
            ChangeEntry(
                vendor_name=vendor_names.get(vid, "(unknown vendor)"),
                vendor_id=vid,
                change_type="added" if version <= 1 else "amended",
                register_version=version,
                changed_at=lg.created_at,
                changed_by=lg.actor,
                fields_changed=lg.detail.get("changed", []),
            )
        )

    current_version = max((c.register_version for c in contracts.values()), default=0)

    return RegisterChangelog(
        since=since,
        until=datetime.now(tz=logs[-1].created_at.tzinfo) if logs else datetime.now(),
        entries=entries,
        previous_export=prev_export,
        current_version=current_version,
    )


def diff_contracts(before: dict, after: dict) -> list[str]:
    """
    Which tracked fields differ. Used by the register endpoint to record a
    precise `changed` list in the audit log rather than just "updated".
    """
    changed = []
    for f in TRACKED_FIELDS:
        if before.get(f) != after.get(f):
            changed.append(f)
    return changed