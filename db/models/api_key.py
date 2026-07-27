"""
Public API keys, cost events, and erasure requests.

Three small tables that Domain 8 owns. Grouped in one module because they
share nothing with the evidence models and don't warrant separate files.

API KEYS ARE NEVER STORED IN PLAINTEXT. We store sha256(key) and a short
non-secret prefix for display. A leaked database gives an attacker hashes,
not credentials.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from db.base import Base, CreatedAtMixin, PgEnum, UUIDPrimaryKeyMixin


class ApiKeyScope(str, enum.Enum):
    READ = "read"
    WRITE = "write"


class ApiKey(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    __tablename__ = "api_keys"

    org_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)

    # sha256 of the full key. The key itself is shown ONCE, at creation.
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    # First 12 chars, for display: "troy_a1b2c3…". Not a secret.
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    scope: Mapped[ApiKeyScope] = mapped_column(
        PgEnum(ApiKeyScope, "api_key_scope"), nullable=False, default=ApiKeyScope.READ
    )
    rate_limit_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False, default=60
    )

    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_api_keys_hash", "key_hash"),)


class ApiCostEvent(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """
    Per-call cost tagging.

    THIS IS THE TABLE THAT RESOLVES PRICING "TBD". Wrik's ai/cost_meter.py and
    the capture layer write here; cost_dashboard.py aggregates to
    cost-per-vendor-per-day. Without it we cannot answer "what does this cost
    to run", which is why the original quoted TBD.
    """

    __tablename__ = "api_cost_events"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), index=True
    )
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("vendors.id"), index=True
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str | None] = mapped_column(String(64))

    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        Index("ix_cost_vendor_created", "vendor_id", "created_at"),
        Index("ix_cost_provider_created", "provider", "created_at"),
    )


class ErasureStatus(str, enum.Enum):
    REQUESTED = "requested"
    EXECUTED = "executed"
    REJECTED = "rejected"


class ErasureRequest(Base, UUIDPrimaryKeyMixin, CreatedAtMixin):
    """
    GDPR Article 17 request log.

    Kept as a tombstone AFTER execution. Proving that an erasure was honoured
    requires a record that it happened — and that record contains only the
    pseudonymous subject_ref, never a name.
    """

    __tablename__ = "erasure_requests"

    subject_ref: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orgs.id"), index=True
    )

    status: Mapped[ErasureStatus] = mapped_column(
        PgEnum(ErasureStatus, "erasure_status"),
        nullable=False,
        default=ErasureStatus.REQUESTED,
    )
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fields_affected: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(Text)
