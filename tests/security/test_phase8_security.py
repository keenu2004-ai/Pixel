"""Hostile Security & Invariant Verification Suite for Phase 8."""

import base64

import numpy as np
import pytest

from packages.contracts.models import (
    ModelFamily,
    ModelMetadata,
    SpeakerEnrollmentRequest,
)
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.local_llm.resource_manager import ModelResourceManager
from services.agent_runtime.local_llm.router import LocalModelRouter
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter
from services.voice_gateway.voice_clone.enrollment import VoiceEnrollmentManager


def _make_audio_sample() -> str:
    num_samples = 24000
    t = np.linspace(0, 1.5, num_samples, endpoint=False, dtype=np.float32)
    sig = np.sin(2 * np.pi * 220 * t) * 0.5
    noise = np.random.normal(0, 0.01, num_samples).astype(np.float32)
    waveform = ((sig + noise) * 32767).astype(np.int16)
    return base64.b64encode(waveform.tobytes()).decode()


def test_invariant_consent_token_mandatory_for_voice_enrollment() -> None:
    manager = VoiceEnrollmentManager()
    b64_sample = _make_audio_sample()

    # Empty token
    with pytest.raises(PermissionError, match="consent token"):
        manager.enroll_voice(
            SpeakerEnrollmentRequest(
                user_id="attacker",
                speaker_name="Cloned Target",
                consent_token="",
                audio_samples_pcm_base64=[b64_sample],
            )
        )

    # Too short / bogus token
    with pytest.raises(PermissionError, match="consent token"):
        manager.enroll_voice(
            SpeakerEnrollmentRequest(
                user_id="attacker",
                speaker_name="Cloned Target",
                consent_token="short",
                audio_samples_pcm_base64=[b64_sample],
            )
        )


def test_invariant_cross_user_profile_access_forbidden() -> None:
    manager = VoiceEnrollmentManager()
    b64_sample = _make_audio_sample()

    profile = manager.enroll_voice(
        SpeakerEnrollmentRequest(
            user_id="victim-user",
            speaker_name="Victim Voice",
            consent_token="valid_consent_token_for_victim_user_12345",
            audio_samples_pcm_base64=[b64_sample],
        )
    )

    # Attacker tries to delete victim's voice profile
    with pytest.raises(PermissionError, match="another user"):
        manager.delete_profile(profile.speaker_id, user_id="attacker-user")


def test_invariant_tampered_model_integrity_rejected() -> None:
    mgr = ModelResourceManager()
    meta = ModelMetadata(
        model_id="compromised-model",
        model_name="Tampered Model",
        family=ModelFamily.QWEN,
        file_path="compromised.gguf",
        sha256_hash="0000000000000000000000000000000000000000000000000000000000000000",
    )
    tampered_bytes = b"MALICIOUS_MODEL_WEIGHTS_AND_PAYLOAD"

    # Integrity verification fails against wrong hash
    assert mgr.verify_model_integrity(meta, file_content=tampered_bytes) is False


def test_invariant_local_model_cannot_bypass_l6_policy() -> None:
    policy_gate = AgentPolicyGate()

    # Tool spec for destructive command
    tool_spec = ToolSpec(
        name="delete_database",
        description="Drops database",
        parameters_schema={},
        risk_class=RiskClass.HIGH_IMPACT,
        requires_approval=True,
    )

    # Evaluating policy for high-impact tool strictly denies or requires approval
    decision, approval_card = policy_gate.evaluate(
        tool_spec=tool_spec,
        arguments={"database": "production"},
        task_id="task-1",
        session_id="session-1",
        user_id="user-1",
    )

    assert decision.verdict.value == "REQUIRE_USER_CONFIRMATION"
    assert approval_card is not None
    assert approval_card.tool_name == "delete_database"


@pytest.mark.asyncio
async def test_invariant_silent_remote_fallback_prevented() -> None:
    intent_engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())

    # Create router with remote fallback explicitly disabled (default)
    router = LocalModelRouter(intent_engine=intent_engine, allow_remote_fallback=False)

    # Simulate local LLM failure by pointing to non-existent model or exception
    class FailingLLM:
        async def generate_response(self, req: object) -> object:
            raise RuntimeError("Out of VRAM")

    router.local_llm = FailingLLM()  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="remote fallback is disabled"):
        await router.route_and_execute("Complex query with failed local LLM")
