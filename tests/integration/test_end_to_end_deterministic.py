"""End-to-End Integration Tests for Phase 2 Deterministic Voice Pipeline."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.contracts.events import (
    AudioFrame,
    TranscriptEvent,
    VADEvent,
    VADState,
    VoiceState,
)
from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter
from services.voice_gateway.pipeline import VoicePipeline
from services.voice_gateway.session import VoiceSession


@pytest.fixture
def mock_adapter() -> MockOSAdapter:
    return MockOSAdapter()


@pytest.fixture
def intent_engine(mock_adapter: MockOSAdapter) -> DeterministicIntentEngine:
    return DeterministicIntentEngine(os_adapter=mock_adapter)


@pytest.mark.asyncio
async def test_end_to_end_timer_voice_flow(
    mock_adapter: MockOSAdapter,
    intent_engine: DeterministicIntentEngine,
) -> None:
    # 1. Setup providers
    vad = MagicMock()
    wake = MagicMock()
    stt = MagicMock()
    tts = MagicMock()

    # Speech ends with user saying "10 minute ka timer laga do"
    vad.process_frame = AsyncMock(return_value=VADEvent(session_id="s_e2e", state=VADState.SPEECH_END))
    stt.transcribe_once = AsyncMock(
        return_value=TranscriptEvent(
            session_id="s_e2e",
            text="10 minute ka timer laga do",
            is_final=True,
            language="hi",
            provider="local_whisper",
        )
    )

    synthesized_audio_chunks = []

    async def _mock_tts_stream(text: str) -> AsyncIterator[bytes]:
        synthesized_audio_chunks.append(text)
        yield b"TTS_AUDIO_BYTES_001"

    tts.synthesize_stream = _mock_tts_stream

    # 2. Build Pipeline
    pipeline = VoicePipeline(
        vad_provider=vad,
        wake_provider=wake,
        stt_provider=stt,
        tts_provider=tts,
        intent_engine=intent_engine,
    )
    session = VoiceSession(session_id="s_e2e")
    session.transition_to(VoiceState.LISTENING)

    # 3. Process frame triggering speech end
    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    outputs = []
    async for item in pipeline.process_frame(frame, session):
        outputs.append(item)

    # 4. Verify OS Adapter State: Timer must be active
    assert len(mock_adapter.timers) == 1
    timer_entry = list(mock_adapter.timers.values())[0]
    assert timer_entry["duration_seconds"] == 600
    assert timer_entry["status"] == "RUNNING"

    # 5. Verify Structured Response text sent to TTS
    assert len(synthesized_audio_chunks) == 1
    assert "10 minute ka timer shuru kar diya hai" in synthesized_audio_chunks[0]

    # 6. Verify final state transitioned back to IDLE
    assert session.state == VoiceState.IDLE


@pytest.mark.asyncio
async def test_end_to_end_alarm_voice_flow(
    mock_adapter: MockOSAdapter,
    intent_engine: DeterministicIntentEngine,
) -> None:
    vad = MagicMock()
    wake = MagicMock()
    stt = MagicMock()
    tts = MagicMock()

    vad.process_frame = AsyncMock(return_value=VADEvent(session_id="s_alarm", state=VADState.SPEECH_END))
    stt.transcribe_once = AsyncMock(
        return_value=TranscriptEvent(
            session_id="s_alarm",
            text="kal subah 7 baje alarm laga dena",
            is_final=True,
            language="hi",
            provider="local_whisper",
        )
    )

    spoken_responses = []

    async def _mock_tts_stream(text: str) -> AsyncIterator[bytes]:
        spoken_responses.append(text)
        yield b"ALARM_AUDIO"

    tts.synthesize_stream = _mock_tts_stream

    pipeline = VoicePipeline(
        vad_provider=vad,
        wake_provider=wake,
        stt_provider=stt,
        tts_provider=tts,
        intent_engine=intent_engine,
    )
    session = VoiceSession(session_id="s_alarm")
    session.transition_to(VoiceState.LISTENING)

    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    async for _ in pipeline.process_frame(frame, session):
        pass

    assert len(mock_adapter.alarms) == 1
    assert "07:00 AM ka alarm set kar diya hai" in spoken_responses[0]


@pytest.mark.asyncio
async def test_end_to_end_volume_flow(
    mock_adapter: MockOSAdapter,
    intent_engine: DeterministicIntentEngine,
) -> None:
    vad = MagicMock()
    wake = MagicMock()
    stt = MagicMock()
    tts = MagicMock()

    vad.process_frame = AsyncMock(return_value=VADEvent(session_id="s_vol", state=VADState.SPEECH_END))
    stt.transcribe_once = AsyncMock(
        return_value=TranscriptEvent(
            session_id="s_vol",
            text="volume 80 percent karo",
            is_final=True,
            language="hi",
            provider="local_whisper",
        )
    )

    spoken_responses = []

    async def _mock_tts_stream(text: str) -> AsyncIterator[bytes]:
        spoken_responses.append(text)
        yield b"VOL_AUDIO"

    tts.synthesize_stream = _mock_tts_stream

    pipeline = VoicePipeline(
        vad_provider=vad,
        wake_provider=wake,
        stt_provider=stt,
        tts_provider=tts,
        intent_engine=intent_engine,
    )
    session = VoiceSession(session_id="s_vol")
    session.transition_to(VoiceState.LISTENING)

    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    async for _ in pipeline.process_frame(frame, session):
        pass

    assert mock_adapter.current_volume == 80
    assert "Volume 80 percent par set kar diya hai" in spoken_responses[0]
