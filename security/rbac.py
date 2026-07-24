"""
Role-based access + row-level vendor scoping.

Two rules that are easy to get wrong:

  1. org_id ALWAYS comes from the verified token, never from a request body
     or query parameter. A client-supplied org id is an IDOR waiting to
     happen.

  2. Per-user vendor restriction is OPT-IN. Absence of OrgVendorAccess rows
     means "all vendors in the org". Opt-out would mean a provisioning bug
     silently grants access to everything.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models.org import OrgRole, OrgVendorAccess
from db.models.vendor import Vendor

# What each role may do. Deliberately explicit rather than inherited, so
# reading this table IS the policy.
PERMISSIONS: dict[OrgRole, set[str]] = {
    OrgRole.OWNER: {
        "vendor:read", "vendor:write", "vendor:delete",
        "signal:read", "signal:dispute",
        "contract:read", "contract:write",
        "alert:read", "alert:ack",
        "export:run",
        "apikey:manage", "user:manage", "gdpr:erase",
    },
    OrgRole.ADMIN: {
        "vendor:read", "vendor:write", "vendor:delete",
        "signal:read", "signal:dispute",
        "contract:read", "contract:write",
        "alert:read", "alert:ack",
        "export:run",
        "apikey:manage", "user:manage", "gdpr:erase",
    },
    OrgRole.ANALYST: {
        "vendor:read", "vendor:write",
        "signal:read", "signal:dispute",
        "contract:read", "contract:write",
        "alert:read", "alert:ack",
        "export:run",
    },
    OrgRole.VIEWER: {
        "vendor:read", "signal:read", "contract:read", "alert:read",
    },
}


def has_permission(role: OrgRole, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())


def require_permission(role: OrgRole, permission: str) -> None:
    if not has_permission(role, permission):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            f"Role '{role.value}' lacks permission '{permission}'",
        )


async def accessible_vendor_ids(
    session: AsyncSession, org_id: uuid.UUID, user_id: uuid.UUID | None
) -> list[uuid.UUID] | None:
    """
    Returns None when the user may see ALL org vendors (the common case),
    or an explicit list when restrictions exist.

    None is meaningfully different from [] — the latter means "restricted to
    nothing", and conflating them would silently open access.
    """
    if user_id is None:
        return None

    rows = (
        await session.execute(
            select(OrgVendorAccess.vendor_id).where(OrgVendorAccess.user_id == user_id)
        )
    ).scalars().all()

    return list(rows) if rows else None


def scope_vendor_query(
    stmt: Select, org_id: uuid.UUID, vendor_ids: list[uuid.UUID] | None
) -> Select:
    """Apply org + optional per-user vendor scoping to any vendor query."""
    stmt = stmt.where(Vendor.org_id == org_id)
    if vendor_ids is not None:
        stmt = stmt.where(Vendor.id.in_(vendor_ids))
    return stmt


async def assert_vendor_access(
    session: AsyncSession,
    org_id: uuid.UUID,
    user_id: uuid.UUID | None,
    vendor_id: uuid.UUID,
) -> None:
    """404, not 403, on a vendor in another org — do not confirm it exists."""
    v = (
        await session.execute(
            select(Vendor.id).where(Vendor.id == vendor_id, Vendor.org_id == org_id)
        )
    ).scalar_one_or_none()
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")

    allowed = await accessible_vendor_ids(session, org_id, user_id)
    if allowed is not None and vendor_id not in allowed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Vendor not found")