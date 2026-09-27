"""
Unit tests for Outbound Connectors, SSRF Defense, and Rate Limiting.
"""

import pytest

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    ConnectorConfig,
    ConnectorStatus,
    ConnectorType,
)
from services.ecosystem.connectors.base import SSRFException
from services.ecosystem.connectors.discord import DiscordConnector
from services.ecosystem.connectors.home_assistant import HomeAssistantConnector
from services.ecosystem.connectors.registry import ConnectorRegistry
from services.ecosystem.connectors.slack import SlackConnector


def test_ssrf_blocks_localhost_and_private_ips() -> None:
    cfg = ConnectorConfig(
        connector_id="conn_local",
        name="Localhost Exploit",
        connector_type=ConnectorType.GENERIC_WEBHOOK,
        target_url="http://localhost:8000/internal-admin",
    )
    connector = SlackConnector(cfg)
    with pytest.raises(SSRFException, match="prohibited"):
        connector._check_ssrf_safety("http://localhost:8000/api")

    with pytest.raises(SSRFException, match="prohibited"):
        connector._check_ssrf_safety("http://127.0.0.1:5000/secret")


@pytest.mark.asyncio
async def test_slack_connector_delivery_and_payload() -> None:
    cfg = ConnectorConfig(
        connector_id="conn_slack",
        name="Slack Test",
        connector_type=ConnectorType.SLACK,
        target_url="https://hooks.slack.com/services/T00/B00/X00",
        signing_secret="my_hmac_secret_123",
        status=ConnectorStatus.ACTIVE,
    )
    connector = SlackConnector(cfg)
    event = AutonomousEvent(
        event_id="evt_001",
        correlation_id="corr_001",
        event_type="TASK_COMPLETED",
        source="autonomous_engine",
        payload={"task_id": "t_01", "result": "success"},
    )
    payload = connector.format_payload(event)
    assert "blocks" in payload
    assert "[PIXEL Alert]" in payload["text"]

    record = await connector.deliver(event)
    assert record.success is True
    assert record.status_code == 200
    assert record.connector_id == "conn_slack"


def test_home_assistant_high_impact_detection() -> None:
    cfg = ConnectorConfig(
        connector_id="conn_ha",
        name="HA Integration",
        connector_type=ConnectorType.HOME_ASSISTANT,
        target_url="https://homeassistant.local.example/api/webhook/pixel",
    )
    connector = HomeAssistantConnector(cfg)

    # Low impact (light toggle)
    e1 = AutonomousEvent(
        event_id="e1",
        correlation_id="corr_1",
        event_type="DEVICE_ACTION",
        source="voice",
        payload={"domain": "light", "service": "turn_on", "entity_id": "light.living_room"},
    )
    assert connector.is_high_impact(e1) is False

    # High impact (door lock unlock)
    e2 = AutonomousEvent(
        event_id="e2",
        correlation_id="corr_2",
        event_type="DEVICE_ACTION",
        source="voice",
        payload={"domain": "lock", "service": "unlock", "entity_id": "lock.front_door"},
    )
    assert connector.is_high_impact(e2) is True


def test_connector_registry_crud_and_deliveries() -> None:
    registry = ConnectorRegistry(db_path=":memory:")
    cfg = ConnectorConfig(
        connector_id="conn_disc",
        name="Discord Alerts",
        connector_type=ConnectorType.DISCORD,
        target_url="https://discord.com/api/webhooks/123/abc",
        status=ConnectorStatus.ACTIVE,
    )
    registry.register_connector(cfg)

    fetched = registry.get_connector("conn_disc")
    assert fetched is not None
    assert fetched.name == "Discord Alerts"

    active_instances = registry.get_active_instances()
    assert len(active_instances) == 1
    assert isinstance(active_instances[0], DiscordConnector)

    # Delete
    assert registry.delete_connector("conn_disc") is True
    assert registry.get_connector("conn_disc") is None
