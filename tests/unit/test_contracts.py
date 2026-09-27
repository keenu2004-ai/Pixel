"""Unit tests for PIXEL event, tool, and intent contracts."""

from packages.contracts.events import AudioFrame, TranscriptEvent, VoiceState
from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.contracts.tools import RiskClass, ToolExecutionRequest, ToolExecutionResult, ToolSpec


def test_voice_states() -> None:
    assert VoiceState.LISTENING == "LISTENING"
    assert VoiceState.THINKING == "THINKING"
    assert VoiceState.SPEAKING == "SPEAKING"
    assert len(VoiceState) == 11


def test_audio_frame_contract() -> None:
    frame = AudioFrame(
        sample_rate=16000,
        channels=1,
        pcm_data=b"\x00\x01\x02\x03",
        timestamp_ms=1000
    )
    assert frame.sample_rate == 16000
    assert len(frame.pcm_data) == 4


def test_transcript_event_contract() -> None:
    event = TranscriptEvent(
        text="kal subah 7 baje mujhe utha dena",
        is_final=True,
        confidence=0.98,
        language="hi-Latn"
    )
    assert event.is_final is True
    assert event.language == "hi-Latn"


def test_tool_spec_and_execution() -> None:
    spec = ToolSpec(
        name="create_alarm",
        description="Sets an alarm on the device clock",
        risk_class=RiskClass.REVERSIBLE_WRITE,
        parameters_schema={"type": "object", "required": ["time"]}
    )
    assert spec.risk_class == RiskClass.REVERSIBLE_WRITE

    req = ToolExecutionRequest(
        tool_name="create_alarm",
        arguments={"time": "07:00"},
        session_id="sess_123",
        trace_id="tr_456"
    )
    assert req.tool_name == "create_alarm"

    res = ToolExecutionResult(
        success=True,
        output={"alarm_id": "alarm_7am"},
        duration_ms=45
    )
    assert res.success is True
    assert res.duration_ms == 45


def test_intent_packet() -> None:
    packet = IntentPacket(
        raw_query="kal subah 7 baje alarm laga dena",
        language="hi-Latn",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="alarm.create",
        extracted_entities={"time": "07:00", "day_offset": 1}
    )
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH
    assert packet.target_intent == "alarm.create"
