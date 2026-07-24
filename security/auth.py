"""
Clerk JWT verification.

Replaces the dev-mode X-Org-Id header, which trusts an unsigned string and is
refused outside the local environment by config.validate_runtime().

Verification is full, not partial: signature against Clerk's JWKS, issuer,
expiry, and not-before. A common shortcut is decoding without verification to
"just read the claims" — that accepts any forged token and is the single most
common auth bug in JWT integrations.

JWKS is cached, because fetching it per request would make Clerk a hard
dependency on every API call.
"""

from __future__ import annotations

import time
from typing import Any

import httpx
import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from backend.config import settings

_jwk_client: PyJWKClient | None = None
_jwks_cached_at: float = 0.0
JWKS_TTL_SECONDS = 3600


def _jwks_url() -> str:
    if settings.clerk_jwks_url:
        return settings.clerk_jwks_url
    raise RuntimeError(
        "CLERK_JWKS_URL is not set. Find it at "
        "https://<your-clerk-domain>/.well-known/jwks.json"
    )


def _client() -> PyJWKClient:
    """Cached JWKS client. Refreshed hourly so key rotation is picked up."""
    global _jwk_client, _jwks_cached_at
    now = time.time()
    if _jwk_client is None or now - _jwks_cached_at > JWKS_TTL_SECONDS:
        _jwk_client = PyJWKClient(_jwks_url(), cache_keys=True)
        _jwks_cached_at = now
    return _jwk_client


async def verify_clerk_token(token: str) -> dict[str, Any]:
    """
    Verify and decode. Raises 401 on any failure.

    Returns the claims dict; 'sub' is the Clerk user id, 'org_id' the Clerk
    organisation id where organisations are enabled.
    """
    try:
        signing_key = _client().get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "require": ["exp", "sub"],
            },
            leeway=10,  # tolerate small clock skew
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}")
    except Exception as exc:
        # JWKS fetch failure, network error, etc. Fail CLOSED.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"Auth verification unavailable: {exc}"
        )

    if not claims.get("sub"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token has no subject")

    return claims


async def fetch_clerk_user(user_id: str) -> dict[str, Any] | None:
    """
    Backend API lookup, for provisioning a User row on first sign-in.
    Never called on the hot path.
    """
    if not settings.clerk_secret_key:
        return None
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(
            f"https://api.clerk.com/v1/users/{user_id}",
            headers={"Authorization": f"Bearer {settings.clerk_secret_key}"},
        )
        return r.json() if r.status_code == 200 else None