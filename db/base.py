"""
SQLAlchemy declarative base + shared column conventions.

Design rules for this domain:
  1. Nothing in `signals`, `excerpts`, `artifacts`, `corrections` or `audit_log`
     is ever UPDATEd or DELETEd. Enforced at the DB level in append_only.sql.
  2. Every table uses UUID primary keys so IDs can be generated client-side
     without a round trip (needed for hash-chain ordering).
  3. All timestamps are timezone-aware UTC. No naive datetimes anywhere.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, MetaData
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Explicit naming convention so Alembic autogenerate produces stable,
# human-readable constraint names instead of random hashes.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPrimaryKeyMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )


class CreatedAtMixin:
    """
    `created_at` is the wall-clock time the row was written.
    It is NOT the same as `observed_at` on a signal (when the event happened
    in the world) — keep the two distinct or the Type-2 history lies.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
        index=True,
    )
    from sqlalchemy import Enum as SAEnum


def PgEnum(py_enum, name: str) -> SAEnum:
    """
    Enum column that persists the member VALUE, not the NAME.

    Without values_callable, SQLAlchemy stores 'LEADERSHIP_CHANGE' while every
    contract in this system uses 'leadership_change'. Raw SQL filters then
    silently match nothing. Always use this, never sa.Enum directly.
    """
    return SAEnum(
        py_enum,
        name=name,
        values_callable=lambda e: [m.value for m in e],
    )