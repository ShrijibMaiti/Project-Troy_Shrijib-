"""
Vendor identity.

LEI is the primary business key, not the name. This is what makes M&A,
rebrands and subsidiary structures survivable: GLEIF publishes parent/child
relationships, so when an entity is acquired its history follows the LEI
instead of silently breaking on a changed name.

LEI is also a MANDATORY field in the ESAs' ITS register templates, so one
decision satisfies both the identity problem and the register schema.
"""

from __future__ import annotations
from db.base import PgEnum

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class EntityType(str, enum.Enum):
    """Drives which capture sources are used. Public gets EDGAR; private
    routes to Form D / CourtListener / Companies House / Crunchbase."""

    PUBLIC_US = "public_us"
    PUBLIC_EU = "public_eu"
    PRIVATE = "private"
    SUBSIDIARY = "subsidiary"
    GOVERNMENT = "government"
    UNKNOWN = "unknown"


class Vendor(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "vendors"

    # ---- Identity -------------------------------------------------------
    lei: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)

    # Alternate names we search under. Populated from GLEIF "other names"
    # plus manual additions. Used by the query template engine.
    aliases: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )

    # Names that produce false positives (e.g. "Plaid" the fabric).
    # Fed into boolean disambiguation as negative terms.
    negative_terms: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )

    # ---- Source routing -------------------------------------------------
    entity_type: Mapped[EntityType] = mapped_column(
        PgEnum(EntityType, "entity_type"),
        nullable=False,
        default=EntityType.UNKNOWN,
    )
    cik: Mapped[str | None] = mapped_column(String(10), index=True)
    ticker: Mapped[str | None] = mapped_column(String(16))
    companies_house_number: Mapped[str | None] = mapped_column(String(16))
    crunchbase_uuid: Mapped[str | None] = mapped_column(String(64))
    primary_domain: Mapped[str | None] = mapped_column(String(255))
    careers_url: Mapped[str | None] = mapped_column(Text)

    # ---- Corporate structure (from GLEIF relationship records) ----------
    parent_lei: Mapped[str | None] = mapped_column(String(20), index=True)
    ultimate_parent_lei: Mapped[str | None] = mapped_column(String(20), index=True)

    # Set when an entity is superseded (merged/acquired). History is retained;
    # new capture follows successor_lei.
    successor_lei: Mapped[str | None] = mapped_column(String(20))

    # ---- Monitoring config ----------------------------------------------
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_critical: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    capture_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )

    # ---- Freshness (drives the amber StalenessChip in the UI) -----------
    last_capture_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_capture_ok: Mapped[bool | None] = mapped_column(Boolean)

    signals = relationship("Signal", back_populates="vendor", lazy="raise")
    contract = relationship(
        "Contract", back_populates="vendor", uselist=False, lazy="raise"
    )

    __table_args__ = (
        # LEI is exactly 20 alphanumeric characters when present.
        CheckConstraint(
            "lei IS NULL OR lei ~ '^[A-Z0-9]{20}$'", name="lei_format"
        ),
        CheckConstraint(
            "cik IS NULL OR cik ~ '^[0-9]{1,10}$'", name="cik_format"
        ),
        Index("ix_vendors_org_active", "org_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Vendor {self.display_name} lei={self.lei}>"