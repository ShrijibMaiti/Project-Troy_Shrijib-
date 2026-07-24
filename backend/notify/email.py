"""SMTP email. Plain text — deliverability beats decoration for alerts."""

from __future__ import annotations

import asyncio
import smtplib
from email.message import EmailMessage

from backend.config import settings
from backend.notify.base import format_headline
from db.models.alert import Alert

DISCLAIMER = (
    "\n\n---\n"
    "This alert is machine-generated from public sources. It is not a "
    "statement of fact about the vendor and is not financial advice. "
    "Claims carry confidence tiers in the evidence pack. To dispute a "
    "signal, use the correction workflow in the dashboard."
)


class EmailNotifier:
    name = "email"

    def configured(self) -> bool:
        return bool(
            settings.smtp_host and settings.smtp_from and settings.notify_email_list
        )

    async def send(self, alert: Alert, vendor_name: str, url: str) -> bool:
        msg = EmailMessage()
        msg["Subject"] = format_headline(alert, vendor_name)[:180]
        msg["From"] = settings.smtp_from
        msg["To"] = ", ".join(settings.notify_email_list)

        body = (
            f"{alert.headline}\n\n"
            f"Vendor:      {vendor_name}\n"
            f"Severity:    {alert.severity}\n"
            f"Convergence: {alert.convergence_score:.2f} "
            f"(threshold {alert.threshold_value:.2f}, "
            f"version {alert.thresholds_version})\n"
            f"Dimensions:  {alert.dimension_count}\n"
            f"Fired at:    {alert.fired_at.isoformat()}\n"
        )
        if url:
            body += f"\nEvidence: {url}\n"
        msg.set_content(body + DISCLAIMER)

        # smtplib is blocking; keep it off the event loop.
        return await asyncio.to_thread(self._send_sync, msg)

    def _send_sync(self, msg: EmailMessage) -> bool:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(msg)
        return True