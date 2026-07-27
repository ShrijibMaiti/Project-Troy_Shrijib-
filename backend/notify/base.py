"""
Notifier protocol + dispatch.

SEQUENCED AFTER CALIBRATION, DELIBERATELY. These channels exist and are
tested, but stay dark until thresholds.json exists — alerting an unvalidated
score just distributes noise faster, and alert fatigue is how monitoring tools
die in GRC teams.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from backend.config import settings
from db.models.alert import Alert


@runtime_checkable
class Notifier(Protocol):
    name: str

    def configured(self) -> bool: ...
    async def send(self, alert: Alert, vendor_name: str, url: str) -> bool: ...


def _channels() -> list[Notifier]:
    from backend.notify.email import EmailNotifier
    from backend.notify.slack import SlackNotifier
    from backend.notify.webhook import WebhookNotifier

    return [SlackNotifier(), EmailNotifier(), WebhookNotifier()]


def format_headline(alert: Alert, vendor_name: str) -> str:
    dims = ", ".join(
        d.get("dimension", "?") if isinstance(d, dict) else str(d)
        for d in (alert.converged_dimensions or [])
    )
    return (
        f"[{alert.severity.value.upper() if hasattr(alert.severity, 'value') else alert.severity}] "
        f"{vendor_name} — {alert.dimension_count} dimensions converged ({dims})"
    )


async def dispatch(
    alert: Alert, vendor_name: str = "vendor", base_url: str = ""
) -> list[str]:
    """
    Returns the channels that accepted. Never raises: a failed notification
    must not fail the scoring pipeline.
    """
    if not settings.notify_enabled:
        return []

    url = f"{base_url}/vendor/{alert.vendor_id}" if base_url else ""
    delivered: list[str] = []

    for ch in _channels():
        if not ch.configured():
            continue
        try:
            if await ch.send(alert, vendor_name, url):
                delivered.append(ch.name)
        except Exception as exc:
            print(f"[notify] {ch.name} failed: {exc}")

    return delivered
