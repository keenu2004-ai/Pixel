"""
Home Assistant Outbound Connector for PIXEL Events.

Distinguishes read/telemetry events from high-impact device service calls.
High-impact service calls (locks, power switches, alarms) require L6 Policy authorization.
"""

from typing import Any

from packages.contracts.autonomous import AutonomousEvent
from services.ecosystem.connectors.base import BaseConnector


class HomeAssistantConnector(BaseConnector):
    """Integrates PIXEL events with Home Assistant REST / Webhook APIs."""

    HIGH_IMPACT_DOMAINS = {"lock", "alarm_control_panel", "cover", "climate"}

    def is_high_impact(self, event: AutonomousEvent) -> bool:
        """Check if an event payload targets a high-impact physical Home Assistant domain."""
        domain = event.payload.get("domain", "")
        service = event.payload.get("service", "")
        if domain in self.HIGH_IMPACT_DOMAINS or "unlock" in service or "disarm" in service:
            return True
        return False

    def format_payload(self, event: AutonomousEvent) -> dict[str, Any]:
        return {
            "source": "PIXEL_CONTROL_PLANE",
            "event_type": event.event_type,
            "entity_id": event.payload.get("entity_id"),
            "domain": event.payload.get("domain", "homeassistant"),
            "service": event.payload.get("service", "notify"),
            "service_data": event.payload,
            "high_impact": self.is_high_impact(event),
            "timestamp": event.timestamp.isoformat(),
        }
