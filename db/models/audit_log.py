"""
Write audit log.

The hash chain proves the signals table wasn't edited. This proves WHO did
WHAT and WHEN across the whole system. Together they are the evidence story;
either alone is insufficient.

Also append-only. Yes, the audit log has its own audit constraints.
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, PgEnum, UUIDPrimaryKeyMixin


class AuditAction(str, enum.Enum):
    VENDOR_CREATED = "vendor_created"
    VENDOR_UPDATED = "vendor_updated"
    VENDOR_DEACTIVATED = "vendor_deactivated"
    CAPTURE_RUN = "capture_run"
    SIGNAL_INSERTED = "signal_inserted"
    SIGNAL_DISPUTED = "signal_disputed"
    SCORE_COMPUTED = "score_computed"
    ALERT_FIRED = "alert_fired"
    ALERT_ACKNOWLEDGED = "alert_acknowledged"
    ARTIFACT_GENERATED = "artifact_generated"
    CONTRACT_UPDATED = "contract_updated"
    REGISTER_EXPORTED = "register_exported"
    PDF_EXPORTED = "pdf_exported"
    CHAIN_VERIFIED = "chain_verified"
    ERASURE_REQUESTED = "erasure_requested"
    ERASURE_EXECUTED = "erasure_executed"
    CALIBRATION_LOADED = "calibration_loaded"


class AuditLog(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "audit_log"

    action: Mapped[AuditAction] = mapped_column(
        PgEnum(AuditAction, "audit_action"), nullable=False, index=True
    )

    # "system" for unattended jobs, Clerk user id for human actions.
    actor: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    actor_ip: Mapped[str | None] = mapped_column(INET)

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), index=True
    )

    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), index=True
    )

    # Small structured context. Never the full payload — a hash of it instead,
    # so the log stays small and can't leak excerpt text.
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    payload_hash: Mapped[str | None] = mapped_column(String(64))

    note: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_org_created", "org_id", "created_at"),
    )
