"""Unit tests for Bilingual Response Generator."""

from packages.contracts.deterministic import (
    AlarmAction,
    AppAction,
    TimerAction,
    VolumeAction,
)
from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.contracts.tools import ToolExecutionResult
from services.intent_engine.response_generator import ResponseGenerator


def test_timer_response_english() -> None:
    packet = IntentPacket(
        raw_query="set a timer for 10 minutes",
        language="en",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="TIMER",
        extracted_entities={"action": TimerAction.SET, "duration_seconds": 600},
    )
    result = ToolExecutionResult(success=True, output={"status": "RUNNING"})
    resp = ResponseGenerator.generate_response(packet, result)
    assert resp == "Timer set for 10 minute."


def test_timer_response_hindi() -> None:
    packet = IntentPacket(
        raw_query="10 minute ka timer laga do",
        language="hi",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="TIMER",
        extracted_entities={"action": TimerAction.SET, "duration_seconds": 600},
    )
    result = ToolExecutionResult(success=True, output={"status": "RUNNING"})
    resp = ResponseGenerator.generate_response(packet, result)
    assert resp == "10 minute ka timer shuru kar diya hai."


def test_alarm_response_bilingual() -> None:
    # English
    p_en = IntentPacket(
        raw_query="set alarm for 7 am",
        language="en",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="ALARM",
        extracted_entities={"action": AlarmAction.SET, "time_str": "07:00 AM"},
    )
    r_en = ToolExecutionResult(success=True, output={"alarm_id": "a1"})
    assert ResponseGenerator.generate_response(p_en, r_en) == "Alarm set for 07:00 AM."

    # Hindi
    p_hi = IntentPacket(
        raw_query="kal subah 7 baje alarm laga do",
        language="hi",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="ALARM",
        extracted_entities={"action": AlarmAction.SET, "time_str": "07:00 AM"},
    )
    r_hi = ToolExecutionResult(success=True, output={"alarm_id": "a2"})
    assert ResponseGenerator.generate_response(p_hi, r_hi) == "07:00 AM ka alarm set kar diya hai."


def test_volume_response() -> None:
    p_vol = IntentPacket(
        raw_query="volume 60 percent karo",
        language="hi",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="VOLUME",
        extracted_entities={"action": VolumeAction.SET, "level": 60},
    )
    r_vol = ToolExecutionResult(success=True, output=60)
    assert ResponseGenerator.generate_response(p_vol, r_vol) == "Volume 60 percent par set kar diya hai."


def test_app_launch_response() -> None:
    p_app = IntentPacket(
        raw_query="Chrome kholo",
        language="hi",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="APP_LAUNCH",
        extracted_entities={"action": AppAction.OPEN, "app_name": "chrome"},
    )
    r_app = ToolExecutionResult(success=True, output=True)
    assert ResponseGenerator.generate_response(p_app, r_app) == "Chrome open kiya ja raha hai."


def test_error_and_policy_denial_response() -> None:
    p_err = IntentPacket(
        raw_query="launch dangerous script",
        language="en",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="APP_LAUNCH",
        extracted_entities={},
    )
    r_err = ToolExecutionResult(success=False, error="Security Policy Denial: Path outside sandbox")
    resp = ResponseGenerator.generate_response(p_err, r_err)
    assert "blocked by security policy" in resp
