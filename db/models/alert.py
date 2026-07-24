"""
Convergence alerts.

An alert records not just THAT it fired but under which thresholds and which
dimensions converged — so "why did this fire?" is answerable months later,
and so the threshold-preview endpoint can replay history against a candidate
threshold ("this setting would have fired N times").
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class AlertSeverity(str, enum.Enum):
    WATCH = "watch"
    ELEVATED = "elevated"
    CRITICAL = "critical"


class Alert(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "alerts"

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )
    vendor_score_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendor_scores.id"), nullable=False
    )

    severity: Mapped[AlertSeverity] = mapped_column(
        Enum(AlertSeverity, name="alert_severity"), nullable=False
    )
    fired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Which dimensions converged, and how far each moved.
    converged_dimensions: Mapped[list] = mapped_column(JSONB, nullable=False)
    dimension_count: Mapped[int] = mapped_column(Integer, nullable=False)
    convergence_score: Mapped[float] = mapped_column(Float, nullable=False)

    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    thresholds_version: Mapped[str] = mapped_column(String(32), nullable=False)

    headline: Mapped[str] = mapped_column(Text, nullable=False)

    # ---- Delivery (written by backend/notify/) --------------------------
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notify_channels: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # ---- Analyst handling -----------------------------------------------
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_by: Mapped[str | None] = mapped_column(String(128))
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        Index("ix_alerts_vendor_fired", "vendor_id", "fired_at"),
        Index("ix_alerts_open", "is_open", "fired_at"),
    )