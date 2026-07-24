"""
Scores written by Wrik's scoring engine.

Two tables on purpose:
  - DimensionScore: one row per vendor per dimension per run. Carries the raw
    value, the trailing baseline and the z-score SEPARATELY, because the UI
    renders all three (DimensionBar) and collapsing them into one number is
    exactly what made the original engine look like a black box.
  - VendorScore: the composite, with the calibration version that produced it.

`weights_version` matters: a score computed under weights v3 is not comparable
to one computed under v4, and an auditor will ask.
"""

from __future__ import annotations
from db.base import PgEnum

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin
from db.models.signal import SignalMetric


class ConfidenceTier(str, enum.Enum):
    """Legal posture, not decoration. Renders as a badge in UI and PDF."""

    VERIFIED = "verified"        # primary filing, or 2+ independent sources
    REPORTED = "reported"        # one credible source
    UNCONFIRMED = "unconfirmed"  # weak / aggregator only


class DimensionScore(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "dimension_scores"

    vendor_score_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendor_scores.id"), nullable=False, index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )

    dimension: Mapped[SignalMetric] = mapped_column(
        PgEnum(SignalMetric, "signal_metric"), nullable=False
    )

    raw_value: Mapped[float | None] = mapped_column(Float)
    baseline: Mapped[float | None] = mapped_column(Float)   # 12-mo trailing median
    z_score: Mapped[float | None] = mapped_column(Float)
    anomaly_ratio: Mapped[float | None] = mapped_column(Float)  # size-bias fix
    contribution: Mapped[float] = mapped_column(Float, nullable=False)  # weighted

    weight_applied: Mapped[float] = mapped_column(Float, nullable=False)
    # True when convergence context changed this dimension's weight.
    context_conditioned: Mapped[bool] = mapped_column(
        nullable=False, server_default="false"
    )

    confidence: Mapped[ConfidenceTier] = mapped_column(
        PgEnum(ConfidenceTier, "confidence_tier"),
        nullable=False,
        default=ConfidenceTier.UNCONFIRMED,
    )

    # Signal IDs that fed this dimension. Lets the UI jump from a bar to its
    # underlying evidence.
    signal_ids: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    vendor_score = relationship("VendorScore", back_populates="dimensions", lazy="raise")

    __table_args__ = (
        Index("ix_dimension_scores_vendor_dim", "vendor_id", "dimension", "created_at"),
    )


class VendorScore(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "vendor_scores"

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )

    composite: Mapped[float] = mapped_column(Float, nullable=False)
    previous_composite: Mapped[float | None] = mapped_column(Float)
    delta: Mapped[float | None] = mapped_column(Float)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # WHICH CALIBRATION PRODUCED THIS. Non-negotiable for reproducibility.
    weights_version: Mapped[str] = mapped_column(String(32), nullable=False)
    thresholds_version: Mapped[str] = mapped_column(String(32), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(32), nullable=False)

    # Signals excluded because they were disputed/superseded.
    excluded_signal_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    dimensions = relationship(
        "DimensionScore", back_populates="vendor_score", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("composite >= 0 AND composite <= 100", name="composite_range"),
        Index("ix_vendor_scores_vendor_computed", "vendor_id", "computed_at"),
    )