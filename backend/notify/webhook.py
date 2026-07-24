"""
Generic HMAC-signed webhook.

Signed because the receiver has no other way to know the payload came from us,
and an unsigned "your vendor is failing" POST is a phishing vector.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx

from backend.config import settings
from db.models.alert import Alert


class WebhookNotifier:
    name = "webhook"

    def configured(self) -> bool:
        return bool(settings.generic_webhook_url)

    async def send(self, alert: Alert, vendor_name: str, url: str) -> bool:
        payload = {
            "event": "alert.fired",
            "alert_id": str(alert.id),
            "vendor_id": str(alert.vendor_id),
            "vendor_name": vendor_name,
            "severity": str(alert.severity),
            "convergence_score": alert.convergence_score,
            "threshold_value": alert.threshold_value,
            "thresholds_version": alert.thresholds_version,
            "dimension_count": alert.dimension_count,
            "converged_dimensions": alert.converged_dimensions,
            "headline": alert.headline,
            "fired_at": alert.fired_at.isoformat(),
            "evidence_url": url,
            "disclaimer": (
                "Machine-generated from public sources; not a statement of fact."
            ),
        }
        body = json.dumps(payload, separators=(",", ":"), default=str)
        ts = str(int(time.time()))

        headers = {"Content-Type": "application/json", "X-Troy-Timestamp": ts}
        if settings.generic_webhook_secret:
            sig = hmac.new(
                settings.generic_webhook_secret.encode(),
                f"{ts}.{body}".encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Troy-Signature"] = f"sha256={sig}"

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                settings.generic_webhook_url, content=body, headers=headers
            )
            return r.status_code < 300