"""Unit tests for in-process async event dispatcher."""

import pytest

from packages.contracts.events import StateChangeEvent, VoiceState
from packages.core.events import EventDispatcher


@pytest.mark.asyncio
async def test_event_dispatch_and_subscription() -> None:
    dispatcher = EventDispatcher()
    received_events: list[StateChangeEvent] = []

    async def on_state_change(event: StateChangeEvent) -> None:
        received_events.append(event)

    await dispatcher.subscribe(StateChangeEvent, on_state_change)

    event = StateChangeEvent(
        session_id="sess_abc",
        previous_state=VoiceState.IDLE,
        current_state=VoiceState.LISTENING,
        reason="Wake word triggered"
    )

    await dispatcher.publish(event)

    assert len(received_events) == 1
    assert received_events[0].session_id == "sess_abc"
    assert received_events[0].current_state == VoiceState.LISTENING
    assert received_events[0].event_id is not None
    assert received_events[0].correlation_id is not None


@pytest.mark.asyncio
async def test_event_unsubscription() -> None:
    dispatcher = EventDispatcher()
    received_events: list[StateChangeEvent] = []

    async def on_state_change(event: StateChangeEvent) -> None:
        received_events.append(event)

    await dispatcher.subscribe(StateChangeEvent, on_state_change)
    await dispatcher.unsubscribe(StateChangeEvent, on_state_change)

    event = StateChangeEvent(
        session_id="sess_abc",
        previous_state=VoiceState.LISTENING,
        current_state=VoiceState.THINKING
    )

    await dispatcher.publish(event)
    assert len(received_events) == 0
