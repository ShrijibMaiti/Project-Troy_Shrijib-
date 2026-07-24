"""
THE REGISTER JOIN — the half of the product no competitor has.

These are the ESAs' ITS register fields (templates RT.01.01-RT.99.01), entered
manually. That is fine and expected: the value was never in COLLECTING these
fields, it is in JOINING them to live monitoring signals. GRC platforms have
the static half. Monitoring tools have the live half. Nobody joins them.

Field names are kept close to the ITS wording on purpose so
compliance/its_mapping.md can be checked against this file line by line.
"""

from __future__ import annotations
from db.base import PgEnum

import enum
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class SubstitutabilityRating(str, enum.Enum):
    NOT_SUBSTITUTABLE = "not_substitutable"
    HIGHLY_COMPLEX = "highly_complex"
    MEDIUM_COMPLEX = "medium_complex"
    EASILY_SUBSTITUTABLE = "easily_substitutable"


class Contract(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "contracts"

    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, unique=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )

    # ---- Identification --------------------------------------------------
    contractual_arrangement_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_lei: Mapped[str | None] = mapped_column(String(20), index=True)
    provider_legal_name: Mapped[str] = mapped_column(String(512), nullable=False)
    provider_country: Mapped[str | None] = mapped_column(String(2))  # ISO 3166-1

    # ---- Function ---------------------------------------------------------
    function_identifier: Mapped[str | None] = mapped_column(String(64))
    function_name: Mapped[str | None] = mapped_column(Text)
    ict_service_type: Mapped[str | None] = mapped_column(String(128))
    supports_critical_function: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ---- Contract terms ---------------------------------------------------
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    notice_period_days: Mapped[int | None] = mapped_column(Integer)
    governing_law_country: Mapped[str | None] = mapped_column(String(2))
    annual_cost_eur: Mapped[int | None] = mapped_column(Integer)

    # ---- Data & location --------------------------------------------------
    data_location_countries: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    processing_location_countries: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    sensitive_data_involved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )

    # ---- Subcontracting chain ---------------------------------------------
    # [{"lei": "...", "name": "...", "rank": 1, "country": "IE"}]
    subcontractors: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # ---- Resilience -------------------------------------------------------
    substitutability: Mapped[SubstitutabilityRating | None] = mapped_column(
        PgEnum(SubstitutabilityRating, "substitutability_rating")
    )
    exit_plan_exists: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    exit_plan_last_tested: Mapped[date | None] = mapped_column(Date)
    reintegration_possible: Mapped[bool | None] = mapped_column(Boolean)

    # ---- Bookkeeping -------------------------------------------------------
    register_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_reviewed_by: Mapped[str | None] = mapped_column(String(128))

    vendor = relationship("Vendor", back_populates="contract", lazy="raise")

    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="contract_dates_ordered",
        ),
        CheckConstraint(
            "provider_country IS NULL OR provider_country ~ '^[A-Z]{2}$'",
            name="provider_country_iso",
        ),
    )