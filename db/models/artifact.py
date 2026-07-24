"""
IMMUTABLE NARRATIVE ARTIFACTS.

This is the single most important table for the audit story.

An artifact is the rendered narrative PLUS everything needed to explain how it
came to exist: the model, the prompt hash, the exact signal IDs it was built
from, and when. Once written it is never regenerated. When an auditor says
"show me the March report", we RETRIEVE this row — we do not re-run the model,
because re-running a non-deterministic model produces a different document and
that is precisely how an audit trail breaks.

There is deliberately no code path anywhere in this repo that regenerates a
stored artifact.
"""

from __future__ import annotations
from db.base import PgEnum

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class NarrativeArtifact(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "narrative_artifacts"

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )
    vendor_score_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendor_scores.id")
    )

    # ---- The rendered output --------------------------------------------
    narrative_md: Mapped[str] = mapped_column(Text, nullable=False)
    # [{"index": 1, "signal_id": "...", "url": "...", "archive_url": "..."}]
    citations: Mapped[list] = mapped_column(JSONB, nullable=False)

    # ---- Reproducibility metadata (the whole point) ---------------------
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_name: Mapped[str] = mapped_column(String(64), nullable=False)
    input_signal_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # sha256 of narrative_md — lets the PDF and API prove they rendered
    # exactly this text.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # ---- Audit results, stored WITH the artifact ------------------------
    # Layer 1: narrative -> signal
    citation_resolution_pct: Mapped[float | None] = mapped_column(Float)
    distinct_claims: Mapped[int | None] = mapped_column(Integer)
    distinct_citations: Mapped[int | None] = mapped_column(Integer)
    unresolved_count: Mapped[int | None] = mapped_column(Integer)
    # Layer 2: excerpt -> claim
    entailment_fidelity_pct: Mapped[float | None] = mapped_column(Float)
    entailment_sampled: Mapped[int | None] = mapped_column(Integer)
    entailment_failed: Mapped[int | None] = mapped_column(Integer)

    # True when produced by deterministic_fallback.py rather than the model.
    is_fallback: Mapped[bool] = mapped_column(nullable=False, server_default="false")

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_artifacts_content_hash"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="content_hash_format"),
        CheckConstraint("prompt_hash ~ '^[0-9a-f]{64}$'", name="prompt_hash_format"),
        Index("ix_artifacts_vendor_generated", "vendor_id", "generated_at"),
    )