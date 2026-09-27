"""Unit tests for VoicePipeline end-to-end orchestration and barge-in."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from packages.contracts.events import (
    AudioFrame,
    StateChangeEvent,
    TranscriptEvent,
    VADEvent,
    VADState,
    VoiceState,
    WakeEvent,
)
from services.voice_gateway.pipeline import VoicePipeline
from services.voice_gateway.session import VoiceSession


@pytest.fixture
def mock_pipeline_components() -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    vad = MagicMock()
    wake = MagicMock()
    stt = MagicMock()
    tts = MagicMock()
    return vad, wake, stt, tts


@pytest.mark.asyncio
async def test_wake_word_trigger_in_idle(
    mock_pipeline_components: tuple[MagicMock, MagicMock, MagicMock, MagicMock],
) -> None:
    vad, wake, stt, tts = mock_pipeline_components
    vad.process_frame = AsyncMock(return_value=VADEvent(session_id="s1", state=VADState.SILENCE))
    wake.process_frame = AsyncMock(
        return_value=WakeEvent(session_id="s1", phrase="Hey Pixel", confidence=0.95)
    )

    pipeline = VoicePipeline(
        vad_provider=vad, wake_provider=wake, stt_provider=stt, tts_provider=tts
    )
    session = VoiceSession(session_id="s1")

    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    events = []
    async for output in pipeline.process_frame(frame, session):
        events.append(output)

    assert len(events) == 2
    assert isinstance(events[0], WakeEvent)
    assert events[0].phrase == "Hey Pixel"
    assert isinstance(events[1], StateChangeEvent)
    assert events[1].current_state == VoiceState.LISTENING
    assert session.state == VoiceState.LISTENING


@pytest.mark.asyncio
async def test_speech_end_transcribes_and_speaks(
    mock_pipeline_components: tuple[MagicMock, MagicMock, MagicMock, MagicMock],
) -> None:
    vad, wake, stt, tts = mock_pipeline_components
    # VAD reports SPEECH_END
    vad.process_frame = AsyncMock(return_value=VADEvent(session_id="s1", state=VADState.SPEECH_END))
    stt.transcribe_once = AsyncMock(
        return_value=TranscriptEvent(
            session_id="s1",
            text="hello pixel",
            is_final=True,
            language="en",
            provider="mock_stt",
        )
    )

    async def _mock_tts_stream(text: str) -> AsyncIterator[bytes]:
        yield b"AUDIO_CHUNK_1"
        yield b"AUDIO_CHUNK_2"

    tts.synthesize_stream = _mock_tts_stream

    pipeline = VoicePipeline(
        vad_provider=vad, wake_provider=wake, stt_provider=stt, tts_provider=tts
    )
    session = VoiceSession(session_id="s1")
    session.transition_to(VoiceState.LISTENING)

    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    outputs = []
    async for output in pipeline.process_frame(frame, session):
        outputs.append(output)

    # Expected events: THINKING, TranscriptEvent, SPEAKING, AUDIO_CHUNK_1, AUDIO_CHUNK_2, IDLE
    state_changes = [o for o in outputs if isinstance(o, StateChangeEvent)]
    assert any(sc.current_state == VoiceState.THINKING for sc in state_changes)
    assert any(sc.current_state == VoiceState.SPEAKING for sc in state_changes)
    assert any(sc.current_state == VoiceState.IDLE for sc in state_changes)

    audio_chunks = [o for o in outputs if isinstance(o, bytes)]
    assert audio_chunks == [b"AUDIO_CHUNK_1", b"AUDIO_CHUNK_2"]


@pytest.mark.asyncio
async def test_barge_in_interruption_during_speaking(
    mock_pipeline_components: tuple[MagicMock, MagicMock, MagicMock, MagicMock],
) -> None:
    vad, wake, stt, tts = mock_pipeline_components
    # VAD detects speech start during SPEAKING state
    vad.process_frame = AsyncMock(
        return_value=VADEvent(session_id="s1", state=VADState.SPEECH_START, speech_probability=0.99)
    )

    pipeline = VoicePipeline(
        vad_provider=vad, wake_provider=wake, stt_provider=stt, tts_provider=tts
    )
    session = VoiceSession(session_id="s1")
    session.transition_to(VoiceState.SPEAKING)

    frame = AudioFrame(sample_rate=16000, channels=1, pcm_data=b"\x00" * 3200, timestamp_ms=0)
    outputs = []
    async for output in pipeline.process_frame(frame, session):
        outputs.append(output)

    assert session.is_playback_cancelled is True
    assert session.state == VoiceState.LISTENING

    state_changes = [o for o in outputs if isinstance(o, StateChangeEvent)]
    assert len(state_changes) == 2
    assert state_changes[0].current_state == VoiceState.INTERRUPTED
    assert state_changes[1].current_state == VoiceState.LISTENING
