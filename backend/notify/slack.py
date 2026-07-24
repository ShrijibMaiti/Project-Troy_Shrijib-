"""Slack incoming webhook."""

from __future__ import annotations

import httpx

from backend.config import settings
from backend.notify.base import format_headline
from db.models.alert import Alert


class SlackNotifier:
    name = "slack"

    def configured(self) -> bool:
        return bool(settings.slack_webhook_url)

    async def send(self, alert: Alert, vendor_name: str, url: str) -> bool:
        headline = format_headline(alert, vendor_name)
        blocks = [
            {"type": "header", "text": {"type": "plain_text", "text": headline[:150]}},
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Vendor*\n{vendor_name}"},
                    {"type": "mrkdwn", "text": f"*Convergence*\n{alert.convergence_score:.1f}"},
                    {"type": "mrkdwn", "text": f"*Threshold*\n{alert.threshold_value:.1f}"},
                    {"type": "mrkdwn", "text": f"*Dimensions*\n{alert.dimension_count}"},
                ],
            },
            {"type": "section", "text": {"type": "mrkdwn", "text": alert.headline[:2900]}},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"thresholds `{alert.thresholds_version}` · "
                            "machine-generated from public sources; "
                            "not a statement of fact"
                        ),
                    }
                ],
            },
        ]
        if url:
            blocks.append(
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "Open evidence"},
                            "url": url,
                        }
                    ],
                }
            )

        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                settings.slack_webhook_url, json={"text": headline, "blocks": blocks}
            )
            return r.status_code < 300