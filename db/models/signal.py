"""
THE CORE TABLE. Everything else hangs off this.

Type-2 slowly-changing dimension, append-only:
  - A signal is never updated. A changed observation is a NEW row.
  - `valid_to` / `is_current` are NOT stored columns, because storing them
    would require UPDATEing the previous row — which append-only forbids.
    Currency is DERIVED by the `signal_current` view (see append_only.sql).
  - `chain_seq` + `row_hash` + `prev_hash` form the tamper-evident chain.

Hash inputs are frozen. Changing what goes into the hash, or its ordering,
invalidates every chain that came before it. Decide once, on day one.
"""

from __future__ import annotations

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Sequence,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, PgEnum, UUIDPrimaryKeyMixin


class SignalMetric(str, enum.Enum):
    """The six scored dimensions plus supporting metrics."""

    LEADERSHIP_CHANGE = "leadership_change"
    LEGAL_EVENT = "legal_event"
    HEADCOUNT_CHANGE = "headcount_change"
    SENTIMENT = "sentiment"
    NEWS_VOLUME = "news_volume"
    OPEN_ROLES = "open_roles"
    FUNDING_EVENT = "funding_event"  # populated by Form D / Crunchbase
    REGULATORY_FILING = "regulatory_filing"


class SignalSource(str, enum.Enum):
    BRIGHTDATA_MCP = "brightdata_mcp"
    SEC_EDGAR = "sec_edgar"
    SEC_FORM_D = "sec_form_d"
    COURTLISTENER = "courtlistener"
    COMPANIES_HOUSE = "companies_house"
    CRUNCHBASE = "crunchbase"
    GDELT = "gdelt"
    GLEIF = "gleif"
    MANUAL = "manual"


# Global monotonic counter for hash-chain ordering. A BIGSERIAL, not a
# timestamp — clocks go backwards, sequences don't.
signal_chain_seq = Sequence("signal_chain_seq", start=1, increment=1)


class Signal(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "signals"

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )

    metric: Mapped[SignalMetric] = mapped_column(
        PgEnum(SignalMetric, "signal_metric"), nullable=False
    )
    source: Mapped[SignalSource] = mapped_column(
        PgEnum(SignalSource, "signal_source"), nullable=False
    )

    # ---- The observation -------------------------------------------------
    # When the event happened in the world.
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # When we observed it. Type-2 valid_from.
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    # Numeric payload where the metric has one (headcount delta, role count,
    # sentiment -1..1). NULL for purely categorical events.
    value: Mapped[float | None] = mapped_column(Float)
    # Short machine-readable summary of the event.
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    # Structured extras: {"role": "CFO", "direction": "departure", ...}
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ---- Provenance ------------------------------------------------------
    excerpt_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("excerpts.id"), index=True
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    archive_url: Mapped[str | None] = mapped_column(Text)

    # ---- Validation (from ai/validator.py) -------------------------------
    validator_verdict: Mapped[str] = mapped_column(String(16), nullable=False)
    validator_confidence: Mapped[float | None] = mapped_column(Float)
    validator_model_id: Mapped[str | None] = mapped_column(String(64))
    validator_prompt_hash: Mapped[str | None] = mapped_column(String(64))

    # ---- Idempotency -----------------------------------------------------
    # sha256(vendor_id, source_url, event_date, metric). Capture upserts on
    # this, which is what stops reruns duplicating rows.
    dedup_key: Mapped[str] = mapped_column(String(64), nullable=False)

    # ---- HASH CHAIN ------------------------------------------------------
    chain_seq: Mapped[int] = mapped_column(
        BigInteger, signal_chain_seq, nullable=False, unique=True
    )
    prev_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)

    vendor = relationship("Vendor", back_populates="signals", lazy="raise")
    excerpt = relationship("Excerpt", lazy="raise")

    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_signals_dedup_key"),
        CheckConstraint(
            "validator_verdict IN ('accepted','rejected','unreviewed')",
            name="validator_verdict_valid",
        ),
        CheckConstraint("row_hash ~ '^[0-9a-f]{64}$'", name="row_hash_format"),
        CheckConstraint("prev_hash ~ '^[0-9a-f]{64}$'", name="prev_hash_format"),
        # The workhorse index: "give me this vendor's timeline for this metric".
        Index(
            "ix_signals_vendor_metric_observed", "vendor_id", "metric", "observed_at"
        ),
        Index("ix_signals_chain_seq", "chain_seq"),
    )

    def hash_payload(self) -> dict:
        """
        FROZEN. These fields, in this order, are what the row hash covers.
        Adding a field here invalidates every existing chain. Do not touch
        without a documented migration + re-anchor.
        """
        return {
            "id": str(self.id),
            "vendor_id": str(self.vendor_id),
            "metric": self.metric.value,
            "source": self.source.value,
            "event_date": self.event_date.isoformat(),
            "observed_at": self.observed_at.isoformat(),
            "value": self.value,
            "summary": self.summary,
            "payload": self.payload,
            "source_url": self.source_url,
            "excerpt_id": str(self.excerpt_id) if self.excerpt_id else None,
            "dedup_key": self.dedup_key,
        }
