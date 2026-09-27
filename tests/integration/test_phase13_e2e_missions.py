"""Integration tests for PIXEL Phase 13 End-to-End Real-World Assistant Missions."""

from collections.abc import AsyncIterator

import pytest

from packages.contracts.events import AudioFrame, TranscriptEvent, VADEvent, VADState, WakeEvent
from packages.contracts.mobile import AndroidActionPayload, AndroidActionType
from packages.contracts.orchestration import DeviceRole
from packages.core.interfaces.stt import BaseSTTProvider
from packages.core.interfaces.tts import BaseTTSProvider
from packages.core.interfaces.vad import BaseVADProvider
from packages.core.interfaces.wake import BaseWakeProvider
from services.coding.coding_agent import CodingAgent
from services.orchestration.multi_device_runtime import MultiDeviceRuntime
from services.voice_gateway.android_actions import AndroidActionAdapter
from services.voice_gateway.session import VoiceSession
from services.voice_gateway.streaming_loop import StreamingVoiceLoop


class E2EWakeProvider(BaseWakeProvider):
    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        return WakeEvent(phrase="hey_pixel", confidence=0.99, session_id=session_id)

    def is_available(self) -> bool:
        return True

    def get_supported_phrases(self) -> list[str]:
        return ["hey_pixel"]


class E2EVADProvider(BaseVADProvider):
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


class E2ESTTProvider(BaseSTTProvider):
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    async def transcribe_once(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptEvent:
        return TranscriptEvent(
            session_id="s-e2e", text=self.transcript, is_final=True, confidence=0.98
        )

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioFrame], session_id: str, language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        yield TranscriptEvent(
            session_id=session_id, text=self.transcript, is_final=True, confidence=0.98
        )

    def is_available(self) -> bool:
        return True


class E2ETTSProvider(BaseTTSProvider):
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


async def _dummy_frames() -> AsyncIterator[AudioFrame]:
    for i in range(4):
        yield AudioFrame(
            timestamp_ms=i * 32,
            pcm_data=b"\x00\x01" * 512,
            sample_rate=16000,
            channels=1,
        )


@pytest.mark.asyncio
async def test_mission_1_voice_simple_command() -> None:
    """Mission 1: Wake -> STT -> Intent -> Fast Path -> Verification -> TTS."""
    loop = StreamingVoiceLoop(
        wake_provider=E2EWakeProvider(),
        vad_provider=E2EVADProvider(),
        stt_provider=E2ESTTProvider("volume 70 percent kardo"),
        tts_provider=E2ETTSProvider(),
    )
    session = VoiceSession(session_id="mission_1_session")
    trace, chunks = await loop.execute_voice_request(_dummy_frames(), session=session)

    assert trace.status == "SUCCESS"
    assert trace.state_verified
    assert trace.model_used == "deterministic_fast_path"
    assert len(chunks) > 0


@pytest.mark.asyncio
async def test_mission_2_voice_reminder_scheduling() -> None:
    """Mission 2: Voice -> Intent -> Scheduler -> State Verification."""
    loop = StreamingVoiceLoop(
        wake_provider=E2EWakeProvider(),
        vad_provider=E2EVADProvider(),
        stt_provider=E2ESTTProvider("remind me in 10 minutes to take medicine"),
        tts_provider=E2ETTSProvider(),
    )
    session = VoiceSession(session_id="mission_2_session")
    trace, chunks = await loop.execute_voice_request(_dummy_frames(), session=session)

    assert trace.status == "SUCCESS"
    assert trace.state_verified


@pytest.mark.asyncio
async def test_mission_3_android_native_action() -> None:
    """Mission 3: Voice Action -> Android Native Adapter -> Policy Check -> Verification."""
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.ALARM,
        parameters={"hour": 7, "minutes": 30, "message": "Morning Standup"},
    )
    result = await adapter.execute_action(payload)
    assert result.success
    assert result.state_verified
    assert result.result_data.get("alarm", {}).get("hour") == 7


@pytest.mark.asyncio
async def test_mission_4_coding_agent_workflow() -> None:
    """Mission 4: Coding Agent Task Execution."""
    agent = CodingAgent()
    state = await agent.execute_task(
        user_query="Inspect code symbols and check test status",
        session_id="mission_4_sess",
    )
    assert state.status.value in ("SUCCESS", "COMPLETED", "EXECUTING", "INITIALIZING")


@pytest.mark.asyncio
async def test_mission_5_multi_device_handoff() -> None:
    """Mission 5: Multi-Device Mesh Handoff (Phone -> Server -> PC)."""
    runtime = MultiDeviceRuntime()
    runtime.register_device("phone-01", DeviceRole.MOBILE_NODE)
    runtime.register_device("pc-01", DeviceRole.PRIMARY_PC)

    handoff = await runtime.initiate_handoff(
        origin_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task_e2e_handoff",
        session_id="sess_e2e_5",
        user_id="user_v",
        context_data={"command": "open_project"},
    )
    res = await runtime.complete_handoff(
        handoff_id=handoff.handoff_id,
        result_payload={"window_opened": True},
        success=True,
    )
    assert res.success
    assert res.response_payload.get("window_opened") is True
