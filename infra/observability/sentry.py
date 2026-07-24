"""
Sentry.

send_default_pii is FALSE and stays false. This system processes personal
data about named executives under a legitimate-interest basis; shipping it to
a third-party error tracker is outside that basis.

A before_send hook scrubs anything that slips through anyway.
"""

from __future__ import annotations

import os
from typing import Any

SCRUB_KEYS = {
    "password", "secret", "token", "api_key", "authorization",
    "shred_master_key", "clerk_secret_key", "database_url",
    "exec_name", "subject_name", "excerpt", "narrative_md",
}


def _scrub(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("[scrubbed]" if k.lower() in SCRUB_KEYS else _scrub(v))
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def before_send(event: dict, hint: dict) -> dict | None:
    event = _scrub(event)
    if "request" in event and isinstance(event["request"], dict):
        event["request"].pop("cookies", None)
        headers = event["request"].get("headers", {})
        for h in ("authorization", "x-api-key", "cookie"):
            headers.pop(h, None)
    return event


def init_sentry(component: str = "api") -> bool:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False

    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=dsn,
        environment=os.getenv("ENVIRONMENT", "local"),
        release=os.getenv("RELEASE", "troy@0.1.0"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_RATE", "0.1")),
        profiles_sample_rate=0.0,
        send_default_pii=False,  # non-negotiable
        before_send=before_send,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
    )
    sentry_sdk.set_tag("component", component)
    return True