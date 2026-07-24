"""
Analyst dispute / correction.

One mechanism, two problems solved:
  1. Methodology — analysts need an override path when a signal is wrong.
  2. Legal — publishing adverse claims about named companies without a
     correction route is indefensible.

Append-only: the original signal STAYS. A correction is a new row that
supersedes it. Nothing is edited, nothing is deleted, and the score recomputes
excluding superseded signals.

This is why the UI must say "supersede and annotate", never "edit".
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class CorrectionReason(str, enum.Enum):
    WRONG_ENTITY = "wrong_entity"          # right event, wrong company
    FACTUALLY_INCORRECT = "factually_incorrect"
    DUPLICATE = "duplicate"
    STALE = "stale"                        # old news resurfacing as new
    MISCLASSIFIED = "misclassified"        # right event, wrong metric
    VENDOR_DISPUTED = "vendor_disputed"    # right of reply
    OTHER = "other"


class Correction(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "corrections"

    signal_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("signals.id"), nullable=False, index=True
    )
    # Optional replacement signal, when the analyst supplies a corrected version.
    superseded_by_signal_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("signals.id")
    )

    reason: Mapped[CorrectionReason] = mapped_column(
        Enum(CorrectionReason, name="correction_reason"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)

    actor: Mapped[str] = mapped_column(String(128), nullable=False)  # Clerk user id
    actor_email: Mapped[str | None] = mapped_column(String(255))
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False
    )

    # Score impact, captured at the moment of correction so the UI can show a
    # diff without recomputing history.
    score_before: Mapped[float | None] = mapped_column(Float)
    score_after: Mapped[float | None] = mapped_column(Float)
    recomputed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        # A signal can only be superseded once.
        UniqueConstraint("signal_id", name="uq_corrections_signal"),
        Index("ix_corrections_org_created", "org_id", "created_at"),
    )