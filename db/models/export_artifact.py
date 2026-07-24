"""
Export artifact records.

Content-addressed: `content_hash` is sha256 of the rendered bytes,
`input_hash` is sha256 of everything that determined those bytes. Two exports
with the same input_hash must produce the same content_hash — if they don't,
the renderer is non-deterministic and the reproducibility claim is false.

Append-only, like every other evidence table.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, PgEnum, UUIDPrimaryKeyMixin


class ExportKind(str, enum.Enum):
    EVIDENCE_PACK = "evidence_pack"      # fleet-wide PDF
    VENDOR_REPORT = "vendor_report"      # single-vendor PDF
    ITS_REGISTER = "its_register"        # machine-readable register


class ExportFormat(str, enum.Enum):
    PDF = "pdf"
    ITS_CSV = "its_csv"      # zip of RT.*.csv + manifest
    ITS_JSON = "its_json"


class ExportArtifact(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "export_artifacts"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), index=True
    )

    kind: Mapped[ExportKind] = mapped_column(
        PgEnum(ExportKind, "export_kind"), nullable=False
    )
    fmt: Mapped[ExportFormat] = mapped_column(
        PgEnum(ExportFormat, "export_format"), nullable=False
    )

    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # The chain head at render time. Printed on the document so a third party
    # holding an old export can detect retroactive tampering without DB access.
    chain_head_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    generated_by: Mapped[str] = mapped_column(String(128), nullable=False)

    # Set when a newer export of the same scope exists. The old one is still
    # retrievable — superseded is not deleted.
    superseded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    register_version: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name="export_content_hash_format"
        ),
        Index("ix_export_org_kind_generated", "org_id", "kind", "generated_at"),
    )