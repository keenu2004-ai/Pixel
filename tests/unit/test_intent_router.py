"""Unit tests for Deterministic Capability Router and Policy Enforcement."""

import pytest

from packages.contracts.deterministic import TimerAction
from packages.contracts.intents import IntentPacket, IntentRoutingType
from services.intent_engine.router import DeterministicRouter
from services.os_control.mock_adapter import MockOSAdapter


@pytest.fixture
def mock_adapter() -> MockOSAdapter:
    return MockOSAdapter()


@pytest.fixture
def router(mock_adapter: MockOSAdapter) -> DeterministicRouter:
    return DeterministicRouter(os_adapter=mock_adapter)


@pytest.mark.asyncio
async def test_route_and_execute_timer(router: DeterministicRouter) -> None:
    packet = IntentPacket(
        raw_query="set a timer for 5 minutes",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="TIMER",
        extracted_entities={"action": TimerAction.SET, "duration_seconds": 300, "label": "Tea"},
        session_id="sess_123",
    )
    result = await router.execute_intent(packet)

    assert result.success is True
    assert result.output["duration_seconds"] == 300
    assert result.output["status"] == "RUNNING"
    assert result.duration_ms < 50


@pytest.mark.asyncio
async def test_idempotency_duplicate_execution(router: DeterministicRouter) -> None:
    packet = IntentPacket(
        raw_query="set a timer for 5 minutes",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="TIMER",
        extracted_entities={"action": TimerAction.SET, "duration_seconds": 300, "label": "Tea"},
        session_id="sess_idem",
    )
    # 1st invocation
    res1 = await router.execute_intent(packet)
    assert res1.success is True

    # 2nd invocation with same session and payload
    res2 = await router.execute_intent(packet)
    assert res2.success is True
    assert res1.output["timer_id"] == res2.output["timer_id"]


@pytest.mark.asyncio
async def test_route_unsupported_intent(router: DeterministicRouter) -> None:
    packet = IntentPacket(
        raw_query="launch nuclear missile",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="UNKNOWN_CAPABILITY",
        extracted_entities={},
        session_id="sess_bad",
    )
    result = await router.execute_intent(packet)
    assert result.success is False
    assert "Unsupported" in result.error if result.error else False
