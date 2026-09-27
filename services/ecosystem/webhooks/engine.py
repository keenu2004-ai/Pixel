"""
Outbound Webhook Dispatch Engine.

Listens to PIXEL EventBus events, filters against connector policies,
enforces hop limits to prevent loops, dispatches to active connectors, and logs audit records.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from packages.contracts.autonomous import AutonomousEvent, EventFilter
from services.autonomous.event_bus import EventBus
from services.ecosystem.connectors.registry import ConnectorRegistry

logger = logging.getLogger(__name__)


class WebhookEngine:
    """Dispatches EventBus events to registered external connectors."""

    MAX_HOP_COUNT: int = 3

    def __init__(
        self,
        event_bus: EventBus | None = None,
        connector_registry: ConnectorRegistry | None = None,
    ):
        self.event_bus = event_bus
        self.connector_registry = connector_registry or ConnectorRegistry()
        self._subscription_id: str | None = None
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    def start(self) -> None:
        """Subscribe to the runtime EventBus."""
        if self.event_bus and not self._subscription_id:
            self.event_bus.subscribe(
                subscriber_id="webhook_engine",
                filter_pred=EventFilter(event_type_pattern="*"),
                callback=self._handle_event,
            )
            self._subscription_id = "webhook_engine"
            logger.info("WebhookEngine subscribed to EventBus")

    def stop(self) -> None:
        """Unsubscribe from the runtime EventBus."""
        if self.event_bus and self._subscription_id:
            self.event_bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    async def _handle_event(self, event: AutonomousEvent) -> None:
        """Handler for incoming EventBus events."""
        await self.dispatch_event(event)

    async def dispatch_event(self, event: AutonomousEvent, hop_count: int = 0) -> int:
        """Evaluate matching connectors and dispatch event."""
        if hop_count > self.MAX_HOP_COUNT:
            logger.warning(
                f"Dropping event {event.event_id} due to hop limit ({hop_count} > {self.MAX_HOP_COUNT})"
            )
            return 0

        active_connectors = self.connector_registry.get_active_instances()
        dispatched_count = 0

        for connector in active_connectors:
            cfg = connector.config
            # Filter events
            if (
                not cfg.enabled_events
                or "*" in cfg.enabled_events
                or event.event_type in cfg.enabled_events
            ):
                # Deliver to connector
                record = await connector.deliver(event, hop_count=hop_count)
                self.connector_registry.record_delivery(record)
                dispatched_count += 1

        return dispatched_count
