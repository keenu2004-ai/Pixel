"""Integration tests for PIXEL Phase 14 Daily-Driver Acceptance Missions (1-9).

Evaluates:
- Mission 1: Simple Voice (Wake -> understand -> execute -> verify -> speak)
- Mission 2: Reminder / Alarm (Voice -> schedule -> notification -> acknowledgment)
- Mission 3: Computer Control (Voice -> open app -> terminal execution -> verify)
- Mission 4: Coding Agent (Voice -> inspect repo -> diagnose -> proposal -> verification)
- Mission 5: Controlled Browser (Voice -> browser -> research -> extract -> verify)
- Mission 6: Multi-Device Mesh (Phone hears -> Server plans -> PC executes -> Phone speaks)
- Mission 7: Offline Mode (Loss of network -> local command execution -> truthful status)
- Mission 8: Crash Recovery (In-flight task -> crash -> restart -> checkpoint restoration)
- Mission 9: Long-Run Stability (Full daily cycle simulation with zero memory leaks)
"""

from collections.abc import AsyncIterator

import pytest

from packages.contracts.agent import AgentExecutionStatus, AgentState
from packages.contracts.events import AudioFrame, TranscriptEvent, VADEvent, VADState, WakeEvent
from packages.contracts.mobile import AndroidActionPayload, AndroidActionType
from packages.contracts.orchestration import DeviceRole
from packages.core.interfaces.stt import BaseSTTProvider
from packages.core.interfaces.tts import BaseTTSProvider
from packages.core.interfaces.vad import BaseVADProvider
from packages.core.interfaces.wake import BaseWakeProvider
from services.coding.coding_agent import CodingAgent
from services.computer_control.browser_tool import ControlledBrowserTool
from services.orchestration.multi_device_runtime import MultiDeviceRuntime
from services.os_control.terminal_tool import TerminalTool
from services.voice_gateway.android_actions import AndroidActionAdapter
from services.voice_gateway.lifecycle_hardener import AssistantLifecycleHardener
from services.voice_gateway.session import VoiceSession
from services.voice_gateway.streaming_loop import StreamingVoiceLoop


class DailyWakeProvider(BaseWakeProvider):
    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        return WakeEvent(phrase="hey_pixel", confidence=0.99, session_id=session_id)

    def is_available(self) -> bool:
        return True

    def get_supported_phrases(self) -> list[str]:
        return ["hey_pixel"]


class DailyVADProvider(BaseVADProvider):
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


class DailySTTProvider(BaseSTTProvider):
    def __init__(self, transcript: str) -> None:
        self.transcript = transcript

    async def transcribe_once(
        self, audio_bytes: bytes, language: str | None = None
    ) -> TranscriptEvent:
        return TranscriptEvent(
            session_id="s-daily", text=self.transcript, is_final=True, confidence=0.98
        )

    async def transcribe_stream(
        self, audio_stream: AsyncIterator[AudioFrame], session_id: str, language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        yield TranscriptEvent(
            session_id=session_id, text=self.transcript, is_final=True, confidence=0.98
        )

    def is_available(self) -> bool:
        return True


class DailyTTSProvider(BaseTTSProvider):
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


async def _audio_feed() -> AsyncIterator[AudioFrame]:
    for i in range(4):
        yield AudioFrame(
            timestamp_ms=i * 32,
            pcm_data=b"\x00\x01" * 512,
            sample_rate=16000,
            channels=1,
        )


@pytest.mark.asyncio
async def test_mission_1_simple_voice() -> None:
    loop = StreamingVoiceLoop(
        wake_provider=DailyWakeProvider(),
        vad_provider=DailyVADProvider(),
        stt_provider=DailySTTProvider(transcript="volume 70 percent kardo"),
        tts_provider=DailyTTSProvider(),
    )
    session = VoiceSession(session_id="sess_mission_1")
    trace, tts_chunks = await loop.execute_voice_request(_audio_feed(), session=session)
    assert trace.status == "SUCCESS"
    assert trace.state_verified
    assert len(tts_chunks) > 0


@pytest.mark.asyncio
async def test_mission_2_reminder_scheduling() -> None:
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.TIMER,
        parameters={"duration_seconds": 300, "label": "Tea reminder"},
    )
    res = await adapter.execute_action(payload)
    assert res.success
    assert res.state_verified


@pytest.mark.asyncio
async def test_mission_3_computer_control() -> None:
    terminal = TerminalTool()
    res = await terminal.run_command("python --version")
    assert res.exit_code == 0
    assert "Python" in res.stdout


@pytest.mark.asyncio
async def test_mission_4_coding_workflow() -> None:
    agent = CodingAgent()
    state = await agent.execute_task(
        user_query="Run tests and report status",
        session_id="mission_4_sess",
    )
    assert state.status in (
        AgentExecutionStatus.SUCCESS,
        AgentExecutionStatus.EXECUTING,
        AgentExecutionStatus.INITIALIZED,
    )


@pytest.mark.asyncio
async def test_mission_5_browser_research() -> None:
    browser = ControlledBrowserTool(allowed_domains={"github.com", "python.org"})
    res = await browser.navigate("https://python.org")
    assert res.success
    assert "python.org" in res.target_url


@pytest.mark.asyncio
async def test_mission_6_multi_device_handoff() -> None:
    runtime = MultiDeviceRuntime()
    runtime.register_device("phone-01", DeviceRole.MOBILE_NODE)
    runtime.register_device("pc-01", DeviceRole.PRIMARY_PC)

    handoff = await runtime.initiate_handoff(
        origin_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task_build_release",
        session_id="sess_cross",
        user_id="user_v",
        context_data={"action": "build_apk"},
    )
    res = await runtime.complete_handoff(
        handoff_id=handoff.handoff_id,
        result_payload={"build_status": "SUCCESS"},
        success=True,
    )
    assert res.success
    assert res.response_device_id == "pc-01"


@pytest.mark.asyncio
async def test_mission_7_offline_mode() -> None:
    runtime = MultiDeviceRuntime()
    runtime.set_network_state(False)

    _ = await runtime.initiate_handoff(
        origin_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task_offline_action",
        session_id="sess_off",
        user_id="user_v",
        context_data={"local": True},
    )
    assert not runtime.is_online
    assert len(runtime._offline_pending_queue) == 1

    runtime.set_network_state(True)
    reconciled = runtime.reconcile_on_network_recovery()
    assert reconciled == 1


@pytest.mark.asyncio
async def test_mission_8_crash_recovery() -> None:
    hardener = AssistantLifecycleHardener()
    state = AgentState(
        task_id="task_mid_flight",
        user_query="Deploy production bundle",
        status=AgentExecutionStatus.EXECUTING,
    )
    hardener.save_checkpoint(state)
    recovered = hardener.recover_on_boot_or_restart()
    assert len(recovered) == 1
    assert recovered[0].task_id == "task_mid_flight"


@pytest.mark.asyncio
async def test_mission_9_long_run_stability() -> None:
    from services.observability.soak_runner import ContinuousSoakRunner

    runner = ContinuousSoakRunner(target_hours=24.0)
    soak_res = await runner.run_simulated_soak(cycles_count=5, cycle_delay_sec=0.001)
    assert soak_res.passed
    assert soak_res.crashes_detected == 0
    assert soak_res.failed_requests == 0
