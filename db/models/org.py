"""
Multi-tenancy. Maps Clerk orgs/users to row-level vendor scoping.

This exists early rather than late for a specific reason: retrofitting org
scoping into a built-out UI is miserable, and the Register screen is
meaningless without knowing who edited what.
"""

from __future__ import annotations
from db.base import PgEnum

import enum
import uuid

from sqlalchemy import (
    Boolean,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin


class OrgRole(str, enum.Enum):
    OWNER = "owner"        # billing + everything
    ADMIN = "admin"        # manage vendors, users, thresholds
    ANALYST = "analyst"    # dispute signals, export, acknowledge alerts
    VIEWER = "viewer"      # read-only


class Org(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "orgs"

    clerk_org_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ISO country of the regulated entity — drives data-residency assertions.
    home_country: Mapped[str | None] = mapped_column(String(2))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    users = relationship("User", back_populates="org", lazy="raise")


class User(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[OrgRole] = mapped_column(
        PgEnum(OrgRole, "org_role"), nullable=False, default=OrgRole.VIEWER
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    org = relationship("Org", back_populates="users", lazy="raise")


class OrgVendorAccess(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """
    Optional per-user vendor restriction. Absence of rows for a user means
    "all vendors in the org" — restriction is opt-in, not opt-out.
    """

    __tablename__ = "org_vendor_access"

    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False, index=True
    )

    __table_args__ = (
        UniqueConstraint("user_id", "vendor_id", name="uq_user_vendor_access"),
        Index("ix_org_vendor_access_vendor", "vendor_id"),
    )