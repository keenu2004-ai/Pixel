"""
Discord Outbound Connector for PIXEL Events.
Formats event payloads into Discord Embeds.
"""

from typing import Any

from packages.contracts.autonomous import AutonomousEvent
from services.ecosystem.connectors.base import BaseConnector


class DiscordConnector(BaseConnector):
    """Formats PIXEL events into Discord webhook embeds."""

    def format_payload(self, event: AutonomousEvent) -> dict[str, Any]:
        return {
            "username": "PIXEL Control Plane",
            "avatar_url": "https://raw.githubusercontent.com/keenu2004-ai/Pixel/main/assets/pixel_avatar.png",
            "embeds": [
                {
                    "title": f"PIXEL Event: {event.event_type}",
                    "color": 0x6366F1,  # Indigo
                    "description": f"Event from source `{event.source}`",
                    "fields": [
                        {"name": "Event ID", "value": f"`{event.event_id}`", "inline": True},
                        {"name": "Timestamp", "value": event.timestamp.isoformat(), "inline": True},
                    ],
                    "footer": {"text": "PIXEL Personal AI Operating Layer"},
                }
            ],
        }
