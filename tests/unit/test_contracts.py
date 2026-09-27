"""Unit tests for PIXEL event, tool, intent, and error contracts."""

from packages.contracts.errors import (
    ErrorCategory,
    PolicyDenialException,
    ProviderTimeoutException,
    ToolExecutionException,
)
from packages.contracts.events import (
    AudioFrame,
    StateChangeEvent,
    TranscriptEvent,
    VADEvent,
    VADState,
    VoiceState,
    WakeEvent,
)
from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.contracts.tools import (
    AuditLevel,
    RiskClass,
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolSpec,
)


def test_voice_states() -> None:
    assert VoiceState.LISTENING == "LISTENING"
    assert VoiceState.THINKING == "THINKING"
    assert VoiceState.SPEAKING == "SPEAKING"
    assert len(VoiceState) == 11


def test_audio_frame_contract() -> None:
    frame = AudioFrame(
        sample_rate=16000, channels=1, pcm_data=b"\x00\x01\x02\x03", timestamp_ms=1000
    )
    assert frame.sample_rate == 16000
    assert len(frame.pcm_data) == 4
    # Round-trip JSON serialization
    data = frame.model_dump_json()
    reconstructed = AudioFrame.model_validate_json(data)
    assert reconstructed.sample_rate == frame.sample_rate
    assert reconstructed.pcm_data == frame.pcm_data


def test_vad_and_wake_events() -> None:
    vad = VADEvent(
        session_id="sess_1",
        state=VADState.SPEECH_START,
        speech_probability=0.95,
        energy_level_db=-15.5,
    )
    assert vad.state == VADState.SPEECH_START
    assert vad.session_id == "sess_1"

    wake = WakeEvent(session_id="sess_1", phrase="Hey Pixel", confidence=0.99)
    assert wake.phrase == "Hey Pixel"


def test_transcript_event_contract() -> None:
    event = TranscriptEvent(
        session_id="sess_1",
        text="kal subah 7 baje mujhe utha dena",
        is_final=True,
        confidence=0.98,
        language="hi-Latn",
        provider="indic-conformer",
    )
    assert event.is_final is True
    assert event.language == "hi-Latn"
    assert event.provider == "indic-conformer"


def test_state_change_event() -> None:
    event = StateChangeEvent(
        session_id="sess_1",
        previous_state=VoiceState.IDLE,
        current_state=VoiceState.LISTENING,
        reason="Wake phrase triggered",
    )
    assert event.previous_state == VoiceState.IDLE
    assert event.current_state == VoiceState.LISTENING


def test_tool_spec_and_execution() -> None:
    spec = ToolSpec(
        name="create_alarm",
        description="Sets an alarm on the device clock",
        version="1.0.0",
        risk_class=RiskClass.REVERSIBLE_WRITE,
        parameters_schema={"type": "object", "required": ["time"]},
        audit_level=AuditLevel.BASIC,
    )
    assert spec.risk_class == RiskClass.REVERSIBLE_WRITE
    assert spec.version == "1.0.0"

    req = ToolExecutionRequest(
        tool_name="create_alarm",
        arguments={"time": "07:00"},
        session_id="sess_123",
        trace_id="tr_456",
    )
    assert req.tool_name == "create_alarm"

    res = ToolExecutionResult(
        success=True,
        output={"alarm_id": "alarm_7am"},
        duration_ms=45,
        evidence={"os_confirmation": True},
    )
    assert res.success is True
    assert res.duration_ms == 45
    assert res.evidence == {"os_confirmation": True}


def test_intent_packet() -> None:
    packet = IntentPacket(
        raw_query="kal subah 7 baje alarm laga dena",
        language="hi-Latn",
        routing_type=IntentRoutingType.DETERMINISTIC_FAST_PATH,
        target_intent="alarm.create",
        extracted_entities={"time": "07:00", "day_offset": 1},
    )
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH
    assert packet.target_intent == "alarm.create"


def test_error_hierarchy() -> None:
    err = ToolExecutionException(tool_name="delete_db", error="Permission denied", retryable=False)
    assert err.payload.category == ErrorCategory.TOOL_EXECUTION_ERROR
    assert err.payload.code == "PIXEL_TOOL_FAILURE"
    assert err.payload.retryable is False

    timeout = ProviderTimeoutException(provider_name="groq_whisper", timeout_ms=3000)
    assert timeout.payload.category == ErrorCategory.PROVIDER_TIMEOUT
    assert timeout.payload.retryable is True

    denial = PolicyDenialException(reason="Sandbox traversal blocked")
    assert denial.payload.category == ErrorCategory.POLICY_DENIAL
