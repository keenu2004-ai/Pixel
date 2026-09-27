"""Unit tests for StreamingVoiceLoop and Barge-In Interruption."""

from collections.abc import AsyncIterator

import pytest

from packages.contracts.events import AudioFrame, TranscriptEvent, VADEvent, VADState, WakeEvent
from packages.core.interfaces.stt import BaseSTTProvider
from packages.core.interfaces.tts import BaseTTSProvider
from packages.core.interfaces.vad import BaseVADProvider
from packages.core.interfaces.wake import BaseWakeProvider
from services.voice_gateway.session import VoiceSession
from services.voice_gateway.streaming_loop import StreamingVoiceLoop


class MockWakeProvider(BaseWakeProvider):
    def __init__(self, should_wake: bool = True) -> None:
        self.should_wake = should_wake

    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        if self.should_wake:
            return WakeEvent(phrase="hey_pixel", confidence=0.98, session_id=session_id)
        return None

    def is_available(self) -> bool:
        return True

    def get_supported_phrases(self) -> list[str]:
        return ["hey_pixel", "oye_pixel"]


class MockVADProvider(BaseVADProvider):
    def __init__(self) -> None:
        self.call_count = 0

    async def process_frame(self, frame: AudioFrame, session_id: str) -> VADEvent:
        self.call_count += 1
        if self.call_count <= 2:
            return VADEvent(
                session_id=session_id, state=VADState.SPEECH_START, speech_probability=0.95
            )
        return VADEvent(session_id=session_id, state=VADState.SILENCE, speech_probability=0.10)

    def is_available(self) -> bool:
        return True

    def reset(self, session_id: str | None = None) -> None:
        self.call_count = 0

    async def shutdown(self) -> None:
        pass


class MockSTTProvider(BaseSTTProvider):
    def __init__(self, transcript: str = "volume 50 percent kardo") -> None:
        self.transcript = transcript

    async def transcribe_once(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptEvent:
        return TranscriptEvent(
            session_id="s-mock", text=self.transcript, is_final=True, confidence=0.99
        )

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioFrame], session_id: str, language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        yield TranscriptEvent(
            session_id=session_id, text=self.transcript, is_final=True, confidence=0.99
        )

    def is_available(self) -> bool:
        return True


class MockTTSProvider(BaseTTSProvider):
    async def synthesize_once(
        self, text: str, voice_id: str | None = None, language: str = "en"
    ) -> bytes:
        return b"\x00\x01" * 1024

    async def synthesize_stream(
        self, text: str, voice_id: str | None = None, language: str = "en"
    ) -> AsyncIterator[bytes]:
        for _ in range(3):
            yield b"\x00\x01" * 512

    def is_available(self) -> bool:
        return True


@pytest.mark.asyncio
async def test_streaming_voice_loop_execution() -> None:
    loop = StreamingVoiceLoop(
        wake_provider=MockWakeProvider(should_wake=True),
        vad_provider=MockVADProvider(),
        stt_provider=MockSTTProvider(transcript="volume 50 percent kardo"),
        tts_provider=MockTTSProvider(),
    )

    async def frame_generator() -> AsyncIterator[AudioFrame]:
        for i in range(4):
            yield AudioFrame(
                timestamp_ms=i * 32,
                pcm_data=b"\x00\x01" * 512,
                sample_rate=16000,
                channels=1,
            )

    session = VoiceSession(session_id="test_sess_1")
    trace, chunks = await loop.execute_voice_request(frame_generator(), session=session)

    assert trace.status == "SUCCESS"
    assert trace.state_verified
    assert trace.intent_routing_latency_ms >= 0.0
    assert trace.total_voice_to_response_latency_ms > 0.0
    assert len(chunks) == 3


@pytest.mark.asyncio
async def test_barge_in_interruption() -> None:
    loop = StreamingVoiceLoop(
        wake_provider=MockWakeProvider(),
        vad_provider=MockVADProvider(),
        stt_provider=MockSTTProvider(),
        tts_provider=MockTTSProvider(),
    )

    barge_in = await loop.trigger_barge_in("test_sess_2")
    assert barge_in.session_id == "test_sess_2"
    assert "tts_stream" in barge_in.cancelled_tasks
    assert loop._is_interrupted

    loop.reset_interruption()
    assert not loop._is_interrupted
