"""Unit tests for LocalModelRouter and hybrid execution path."""

import pytest

from services.agent_runtime.local_llm.router import LocalModelRouter
from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter


@pytest.mark.asyncio
async def test_router_deterministic_fast_path() -> None:
    intent_engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())
    router = LocalModelRouter(intent_engine=intent_engine)

    resp, route, telemetry = await router.route_and_execute("kal subah 7 baje alarm laga dena")
    assert route == "DETERMINISTIC_FAST_PATH"
    assert telemetry["tokens_used"] == 0
    assert len(resp) > 0


@pytest.mark.asyncio
async def test_router_local_llm_path() -> None:
    intent_engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())
    router = LocalModelRouter(intent_engine=intent_engine)

    resp, route, telemetry = await router.route_and_execute(
        "Analyze the project structure and suggest improvements",
        tools=[{"name": "list_files", "arguments": {}}],
    )
    assert route == "LOCAL_QUANTIZED_LLM"
    assert telemetry["tokens_used"] > 0
    assert len(resp) > 0
