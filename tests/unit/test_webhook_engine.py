"""
Unit tests for Webhook Dispatch Engine and EventBus Bridge.
"""

import pytest

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
)
from services.autonomous.event_bus import EventBus
from services.ecosystem.connectors.registry import ConnectorRegistry
from services.ecosystem.webhooks.engine import WebhookEngine


@pytest.mark.asyncio
async def test_webhook_engine_event_dispatch() -> None:
    event_bus = EventBus()
    conn_reg = ConnectorRegistry(db_path=":memory:")

    # Register active Slack connector for TASK_COMPLETED
    cfg = ConnectorConfig(
        connector_id="conn_test_01",
        name="Test Slack",
        connector_type=ConnectorType.SLACK,
        target_url="https://hooks.slack.com/services/test/hook",
        enabled_events=["TASK_COMPLETED"],
        status=ConnectorStatus.ACTIVE,
    )
    conn_reg.register_connector(cfg)

    engine = WebhookEngine(event_bus=event_bus, connector_registry=conn_reg)
    engine.start()

    # Publish matching event
    event = AutonomousEvent(
        event_id="evt_test_100",
        correlation_id="corr_test_100",
        event_type="TASK_COMPLETED",
        source="unit_test",
        payload={"task_id": "task_1", "status": "done"},
    )

    dispatched = await engine.dispatch_event(event)
    assert dispatched == 1

    # Check delivery recorded
    deliveries = conn_reg.list_deliveries()
    assert len(deliveries) >= 1
    assert deliveries[0].event_id == "evt_test_100"
    assert deliveries[0].success is True

    # Publish unhandled event
    event_unhandled = AutonomousEvent(
        event_id="evt_test_101",
        correlation_id="corr_test_101",
        event_type="UNRELATED_EVENT",
        source="unit_test",
        payload={},
    )
    dispatched_unhandled = await engine.dispatch_event(event_unhandled)
    assert dispatched_unhandled == 0

    engine.stop()
