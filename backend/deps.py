"""
Dependency injection: session, redis, and the authenticated org context.

Row-level scoping happens HERE, not in each router. Every query that touches
tenant data takes org_id from OrgContext — never from a request body or query
param, because a client-supplied org id is an IDOR waiting to happen.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from db.cache import get_redis
from db.models.org import Org, OrgRole, User
from db.session import SessionFactory

# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DB = Annotated[AsyncSession, Depends(get_db)]


# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------


async def get_cache() -> aioredis.Redis:
    return get_redis()


Cache = Annotated[aioredis.Redis, Depends(get_cache)]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OrgContext:
    org_id: uuid.UUID
    user_id: uuid.UUID | None
    actor: str  # Clerk user id, or "dev" / "system"
    actor_email: str | None
    role: OrgRole

    def can_write(self) -> bool:
        return self.role in (OrgRole.OWNER, OrgRole.ADMIN, OrgRole.ANALYST)

    def can_admin(self) -> bool:
        return self.role in (OrgRole.OWNER, OrgRole.ADMIN)


async def current_org(
    session: DB,
    x_org_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> OrgContext:
    """
    Resolve the caller's org.

    dev mode  — trusts X-Org-Id. Local only; config.validate_runtime() refuses
                to boot with auth_mode='dev' outside the local environment.
    clerk mode — verifies the JWT and maps the Clerk org to our Org row.
                 Implemented in Domain 8 (security/auth.py); wired here.
    """
    if settings.auth_mode == "dev":
        if not x_org_id:
            org = (
                await session.execute(select(Org).where(Org.is_active).limit(1))
            ).scalar_one_or_none()
            if org is None:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED,
                    "No org exists. Seed one, or pass X-Org-Id.",
                )
        else:
            try:
                oid = uuid.UUID(x_org_id)
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "X-Org-Id must be a UUID"
                ) from exc
            org = (
                await session.execute(select(Org).where(Org.id == oid))
            ).scalar_one_or_none()
            if org is None:
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown org")

        return OrgContext(
            org_id=org.id,
            user_id=None,
            actor="dev",
            actor_email=None,
            role=OrgRole.OWNER,
        )

    # --- clerk mode -------------------------------------------------------
    from security.auth import verify_clerk_token  # Domain 8

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")

    claims = await verify_clerk_token(authorization.split(" ", 1)[1])

    user = (
        await session.execute(select(User).where(User.clerk_user_id == claims["sub"]))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User not provisioned")

    return OrgContext(
        org_id=user.org_id,
        user_id=user.id,
        actor=user.clerk_user_id,
        actor_email=user.email,
        role=user.role,
    )


CurrentOrg = Annotated[OrgContext, Depends(current_org)]


def require_write(org: CurrentOrg) -> OrgContext:
    if not org.can_write():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Write access required")
    return org


def require_admin(org: CurrentOrg) -> OrgContext:
    if not org.can_admin():
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return org


Writer = Annotated[OrgContext, Depends(require_write)]
Admin = Annotated[OrgContext, Depends(require_admin)]


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


async def write_audit(
    session: AsyncSession,
    org: OrgContext,
    action,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    detail: dict | None = None,
    note: str | None = None,
) -> None:
    """
    Every mutating endpoint calls this. The hash chain proves the evidence
    wasn't edited; this proves who did what. Neither is sufficient alone.
    """
    from db.models.audit_log import AuditLog

    session.add(
        AuditLog(
            action=action,
            actor=org.actor,
            actor_email=org.actor_email,
            org_id=org.org_id,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail or {},
            note=note,
        )
    )
