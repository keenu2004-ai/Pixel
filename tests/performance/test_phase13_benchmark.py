"""Performance and latency benchmarks for PIXEL Phase 13 Real-World Pipeline."""

import time
from collections.abc import AsyncIterator

import pytest

from packages.contracts.events import AudioFrame, TranscriptEvent, VADEvent, VADState, WakeEvent
from packages.contracts.mobile import AndroidActionPayload, AndroidActionType
from packages.contracts.orchestration import DeviceRole
from packages.core.interfaces.stt import BaseSTTProvider
from packages.core.interfaces.tts import BaseTTSProvider
from packages.core.interfaces.vad import BaseVADProvider
from packages.core.interfaces.wake import BaseWakeProvider
from services.orchestration.multi_device_runtime import MultiDeviceRuntime
from services.voice_gateway.android_actions import AndroidActionAdapter
from services.voice_gateway.session import VoiceSession
from services.voice_gateway.streaming_loop import StreamingVoiceLoop


class BenchWakeProvider(BaseWakeProvider):
    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        return WakeEvent(phrase="hey_pixel", confidence=0.99, session_id=session_id)

    def is_available(self) -> bool:
        return True

    def get_supported_phrases(self) -> list[str]:
        return ["hey_pixel"]


class BenchVADProvider(BaseVADProvider):
    def __init__(self) -> None:
        self.count = 0

    async def process_frame(self, frame: AudioFrame, session_id: str) -> VADEvent:
        self.count += 1
        return VADEvent(
            session_id=session_id,
            state=VADState.SPEECH_START if self.count <= 2 else VADState.SILENCE,
            speech_probability=0.95,
        )

    def is_available(self) -> bool:
        return True

    def reset(self, session_id: str | None = None) -> None:
        self.count = 0

    async def shutdown(self) -> None:
        pass


class BenchSTTProvider(BaseSTTProvider):
    async def transcribe_once(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptEvent:
        return TranscriptEvent(
            session_id="s-bench", text="volume 50 percent", is_final=True, confidence=0.98
        )

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioFrame], session_id: str, language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        yield TranscriptEvent(
            session_id=session_id, text="volume 50 percent", is_final=True, confidence=0.98
        )

    def is_available(self) -> bool:
        return True


class BenchTTSProvider(BaseTTSProvider):
    async def synthesize_once(
        self, text: str, voice_id: str | None = None, language: str = "en"
    ) -> bytes:
        return b"\x00\x01" * 1024

    async def synthesize_stream(
        self, text: str, voice_id: str | None = None, language: str = "en"
    ) -> AsyncIterator[bytes]:
        yield b"\x00\x01" * 512

    def is_available(self) -> bool:
        return True


async def _bench_frames() -> AsyncIterator[AudioFrame]:
    for i in range(4):
        yield AudioFrame(
            timestamp_ms=i * 32,
            pcm_data=b"\x00\x01" * 512,
            sample_rate=16000,
            channels=1,
        )


@pytest.mark.asyncio
async def test_benchmark_voice_loop_latency() -> None:
    loop = StreamingVoiceLoop(
        wake_provider=BenchWakeProvider(),
        vad_provider=BenchVADProvider(),
        stt_provider=BenchSTTProvider(),
        tts_provider=BenchTTSProvider(),
    )

    latencies = []
    for i in range(20):
        session = VoiceSession(session_id=f"bench_sess_{i}")
        t0 = time.perf_counter()
        trace, _ = await loop.execute_voice_request(_bench_frames(), session=session)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

    print("\n--- PIXEL Phase 13 Voice Loop Latency Benchmarks ---")
    print(f"Average Voice-to-Response Latency: {avg_latency:.2f} ms")
    print(f"P95 Voice-to-Response Latency: {p95_latency:.2f} ms")

    # SLA Assertions
    assert avg_latency < 50.0  # < 50ms in simulated loop
    assert p95_latency < 100.0


@pytest.mark.asyncio
async def test_benchmark_android_action_latency() -> None:
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.MEDIA_CONTROL,
        parameters={"command": "SET_VOLUME", "volume": 50},
    )

    latencies = []
    for _ in range(50):
        t0 = time.perf_counter()
        await adapter.execute_action(payload)
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_action_ms = sum(latencies) / len(latencies)
    assert avg_action_ms < 5.0  # Sub-5ms policy check and dispatch


@pytest.mark.asyncio
async def test_benchmark_multi_device_handoff_latency() -> None:
    runtime = MultiDeviceRuntime()
    runtime.register_device("phone-01", DeviceRole.MOBILE_NODE)
    runtime.register_device("pc-01", DeviceRole.PRIMARY_PC)

    latencies = []
    for i in range(30):
        t0 = time.perf_counter()
        handoff = await runtime.initiate_handoff(
            "phone-01", "pc-01", f"t_{i}", f"s_{i}", "u_v", {"cmd": "ping"}
        )
        await runtime.complete_handoff(handoff.handoff_id, {"pong": True})
        latencies.append((time.perf_counter() - t0) * 1000)

    avg_handoff_ms = sum(latencies) / len(latencies)
    assert avg_handoff_ms < 5.0
