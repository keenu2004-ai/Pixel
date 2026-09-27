"""Unit tests for EventBus, predicate filtering, and deduplication."""

import pytest

from packages.contracts.autonomous import AutonomousEvent, EventFilter
from services.autonomous.event_bus import EventBus


@pytest.mark.asyncio
async def test_event_bus_subscription_and_dispatch() -> None:
    bus = EventBus()
    received_events: list[AutonomousEvent] = []

    async def sample_handler(event: AutonomousEvent) -> None:
        received_events.append(event)

    filt = EventFilter(event_type_pattern="system.*")
    bus.subscribe("sub_01", filt, sample_handler)

    event1 = AutonomousEvent(
        event_id="evt_01",
        event_type="system.cpu_high",
        source="desktop_core",
        correlation_id="corr_01",
        payload={"usage_pct": 92.5},
    )

    dispatched = await bus.publish(event1)
    assert dispatched == 1
    assert len(received_events) == 1
    assert received_events[0].event_id == "evt_01"


@pytest.mark.asyncio
async def test_event_bus_deduplication() -> None:
    bus = EventBus(deduplication_window_seconds=60.0)
    received_count = 0

    async def counter_handler(event: AutonomousEvent) -> None:
        nonlocal received_count
        received_count += 1

    bus.subscribe("sub_count", EventFilter(event_type_pattern="*"), counter_handler)

    event = AutonomousEvent(
        event_id="evt_unique_100",
        event_type="device.status",
        source="satellite_living_room",
        correlation_id="corr_100",
        idempotency_key="idempotent_key_abc",
    )

    # First publication succeeds
    count1 = await bus.publish(event)
    assert count1 == 1
    assert received_count == 1

    # Second publication with same idempotency key is dropped
    count2 = await bus.publish(event)
    assert count2 == 0
    assert received_count == 1


@pytest.mark.asyncio
async def test_event_bus_unsubscription() -> None:
    bus = EventBus()
    received: list[str] = []

    async def handler(event: AutonomousEvent) -> None:
        received.append(event.event_id)

    bus.subscribe("sub_temp", EventFilter(event_type_pattern="*"), handler)
    assert bus.unsubscribe("sub_temp")
    assert not bus.unsubscribe("sub_temp")  # Second unsubscription returns False

    event = AutonomousEvent(
        event_id="evt_02",
        event_type="test.event",
        source="test",
        correlation_id="corr_02",
    )
    dispatched = await bus.publish(event)
    assert dispatched == 0
    assert len(received) == 0
