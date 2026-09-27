"""
Matrix Outbound Connector for PIXEL Events.
Formats event payloads into Matrix Client-Server API event format.
"""

from typing import Any

from packages.contracts.autonomous import AutonomousEvent
from services.ecosystem.connectors.base import BaseConnector


class MatrixConnector(BaseConnector):
    """Formats PIXEL events into Matrix m.room.message payloads."""

    def format_payload(self, event: AutonomousEvent) -> dict[str, Any]:
        body = (
            f"[PIXEL Event] {event.event_type} from {event.source} at {event.timestamp.isoformat()}"
        )
        return {
            "msgtype": "m.notice",
            "body": body,
            "format": "org.matrix.custom.html",
            "formatted_body": f"<strong>[PIXEL Event]</strong> <code>{event.event_type}</code><br/><pre>{event.payload}</pre>",
            "pixel_event_id": event.event_id,
        }
