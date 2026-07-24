"""
The stored source text a signal was extracted from.

Two jobs:
  1. It is the input to the extraction-layer (entailment) audit — without it
     we can only prove narrative->row, never row->source.
  2. It is the licensing guardrail. `text` is HARD CAPPED. We store links plus
     short factual extracts, never article bodies. The cap is enforced here at
     the DB level as well as in capture/excerpt.py, because a guardrail that
     lives only in application code is a guardrail that eventually leaks.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

# Keep in sync with capture/excerpt.py::MAX_EXCERPT_CHARS
MAX_EXCERPT_CHARS = 500


class Excerpt(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "excerpts"

    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    archive_url: Mapped[str | None] = mapped_column(Text)  # Wayback snapshot
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_title: Mapped[str | None] = mapped_column(Text)

    # THE CAPPED EXTRACT. Never a full article.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False)

    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # sha256 of the raw fetched content, before extraction. Lets us detect a
    # source page changing under us without storing the page.
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)

    __table_args__ = (
        CheckConstraint(
            f"char_length(text) <= {MAX_EXCERPT_CHARS}",
            name="excerpt_length_cap",
        ),
        CheckConstraint("char_count = char_length(text)", name="char_count_matches"),
        Index("ix_excerpts_content_sha", "content_sha256"),
    )