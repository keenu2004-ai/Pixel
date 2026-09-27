"""Adversarial and Security Attack Tests for Phase 2 Deterministic Pipeline."""

import pytest

from packages.contracts.deterministic import AppAction
from packages.contracts.intents import IntentPacket, IntentRoutingType
from services.intent_engine.parser import DeterministicIntentParser
from services.intent_engine.router import DeterministicRouter
from services.os_control.windows_adapter import WindowsOSAdapter


@pytest.fixture
def windows_adapter(tmp_path: object) -> WindowsOSAdapter:
    import pathlib
    return WindowsOSAdapter(persistence_dir=str(pathlib.Path(str(tmp_path))))


@pytest.fixture
def router(windows_adapter: WindowsOSAdapter) -> DeterministicRouter:
    return DeterministicRouter(os_adapter=windows_adapter)


@pytest.mark.asyncio
async def test_shell_injection_prevention(router: DeterministicRouter) -> None:
    # Attacker tries shell injection via app name
    attack_payloads = [
        "calc.exe; rm -rf /",
        "notepad & format c:",
        "chrome | shutdown /s /t 0",
        "`whoami`",
        "calc && del *.*",
    ]

    for attack in attack_payloads:
        packet = DeterministicIntentParser.parse_intent(f"open {attack}")
        res = await router.execute_intent(packet)
        # Must fail safely without executing dangerous shell command
        assert res.success is False


@pytest.mark.asyncio
async def test_unapproved_app_launch_rejection(router: DeterministicRouter) -> None:
    packet = IntentPacket(
        raw_query="open powershell_injector.exe",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="APP_LAUNCH",
        extracted_entities={"action": AppAction.OPEN, "app_name": "malicious_script.exe"},
        session_id="s_sec",
    )
    result = await router.execute_intent(packet)
    assert result.success is False
    assert "not in the approved whitelist" in str(result.error)


def test_volume_bounds_sanitization() -> None:
    # Attacker inputs negative or absurd volume
    p_neg = DeterministicIntentParser.parse_intent("volume -50 percent karo")
    lvl1 = p_neg.extracted_entities.get("level")
    if lvl1 is not None:
        assert isinstance(lvl1, int) and lvl1 >= 0

    p_overflow = DeterministicIntentParser.parse_intent("volume 500 percent karo")
    lvl2 = p_overflow.extracted_entities.get("level")
    if lvl2 is not None:
        assert isinstance(lvl2, int) and lvl2 <= 100
