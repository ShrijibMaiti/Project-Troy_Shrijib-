"""
Public API keys.

THE KEY IS SHOWN ONCE, AT CREATION, AND NEVER AGAIN. We store sha256(key)
plus a non-secret prefix for display. A database leak yields hashes, not
credentials.

Format: troy_<43 url-safe base64 chars> — the prefix makes keys greppable in
logs and recognisable in secret scanners.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.api_key import ApiKey, ApiKeyScope
from db.models.org import Org
from security.ratelimit import enforce

KEY_PREFIX = "troy_"
PREFIX_DISPLAY_LEN = 12


@dataclass
class ApiKeyContext:
    org_id: uuid.UUID
    key_id: uuid.UUID
    scope: ApiKeyScope
    name: str

    def can_write(self) -> bool:
        return self.scope == ApiKeyScope.WRITE


def generate_key() -> tuple[str, str, str]:
    """Returns (full_key, sha256_hash, display_prefix)."""
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), raw[:PREFIX_DISPLAY_LEN]


async def create_key(
    session: AsyncSession,
    org_id: uuid.UUID,
    name: str,
    created_by: str,
    scope: ApiKeyScope = ApiKeyScope.READ,
    rate_limit_per_minute: int = 60,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    """Returns (row, plaintext_key). Surface the plaintext ONCE, then discard."""
    raw, hashed, prefix = generate_key()
    row = ApiKey(
        org_id=org_id,
        name=name,
        key_hash=hashed,
        key_prefix=prefix,
        scope=scope,
        rate_limit_per_minute=rate_limit_per_minute,
        created_by=created_by,
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return row, raw


async def verify_key(session: AsyncSession, raw_key: str) -> ApiKeyContext:
    """
    Resolve a key to an org context, enforcing its own rate limit.

    Constant-time comparison is unnecessary here: we look up by hash, so
    there's no secret-dependent branch to time.
    """
    if not raw_key.startswith(KEY_PREFIX):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed API key")

    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    row = (
        await session.execute(select(ApiKey).where(ApiKey.key_hash == hashed))
    ).scalar_one_or_none()

    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key")
    if row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key revoked")
    if row.expires_at is not None and row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API key expired")

    org = (await session.execute(select(Org).where(Org.id == row.org_id))).scalar_one_or_none()
    if org is None or not org.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation inactive")

    await enforce(f"apikey:{row.id}", row.rate_limit_per_minute)

    # Best-effort usage stamp; never fail a request over it.
    try:
        row.last_used_at = datetime.now(timezone.utc)
        await session.flush()
    except Exception:
        pass

    return ApiKeyContext(
        org_id=row.org_id, key_id=row.id, scope=row.scope, name=row.name
    )


async def revoke_key(session: AsyncSession, org_id: uuid.UUID, key_id: uuid.UUID) -> ApiKey:
    """Revoke, never delete — the audit trail needs the record."""
    row = (
        await session.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "API key not found")
    row.revoked_at = datetime.now(timezone.utc)
    return row


async def list_keys(session: AsyncSession, org_id: uuid.UUID) -> list[ApiKey]:
    return list(
        (
            await session.execute(
                select(ApiKey).where(ApiKey.org_id == org_id).order_by(ApiKey.created_at.desc())
            )
        ).scalars()
    )