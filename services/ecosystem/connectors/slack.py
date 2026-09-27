"""
Slack Outbound Connector for PIXEL Events.
Formats event payloads into Slack Block Kit message structures.
"""

from typing import Any

from packages.contracts.autonomous import AutonomousEvent
from services.ecosystem.connectors.base import BaseConnector


class SlackConnector(BaseConnector):
    """Formats PIXEL events into Slack Block Kit notifications."""

    def format_payload(self, event: AutonomousEvent) -> dict[str, Any]:
        return {
            "text": f"[PIXEL Alert] {event.event_type}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🤖 PIXEL Event: {event.event_type}",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Event ID:*\n`{event.event_id}`"},
                        {"type": "mrkdwn", "text": f"*Source:*\n`{event.source}`"},
                        {"type": "mrkdwn", "text": f"*Timestamp:*\n{event.timestamp.isoformat()}"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```\n{event.payload}\n```",
                    },
                },
            ],
        }
