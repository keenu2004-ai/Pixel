"""Integration tests for Personalized Voice Cloning and Local Model Pipeline."""

import base64

import numpy as np
import pytest

from packages.contracts.models import (
    SpeakerEnrollmentRequest,
    VoiceSynthesisRequest,
)
from services.agent_runtime.local_llm.provider import QuantizedLocalLLM
from services.agent_runtime.local_llm.router import LocalModelRouter
from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter
from services.voice_gateway.voice_clone.enrollment import VoiceEnrollmentManager
from services.voice_gateway.voice_clone.personalized_tts import PersonalizedTTSProvider
from services.voice_gateway.voice_clone.speaker_encoder import ECAPASpeakerEncoder


def _make_audio_sample() -> str:
    num_samples = 24000
    t = np.linspace(0, 1.5, num_samples, endpoint=False, dtype=np.float32)
    sig = np.sin(2 * np.pi * 220 * t) * 0.5
    noise = np.random.normal(0, 0.01, num_samples).astype(np.float32)
    waveform = ((sig + noise) * 32767).astype(np.int16)
    return base64.b64encode(waveform.tobytes()).decode()


@pytest.mark.asyncio
async def test_end_to_end_voice_cloning_and_local_llm_pipeline() -> None:
    # 1. Setup components
    encoder = ECAPASpeakerEncoder()
    enrollment_mgr = VoiceEnrollmentManager(speaker_encoder=encoder)
    tts = PersonalizedTTSProvider(sample_rate=24000)
    intent_engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())
    local_llm = QuantizedLocalLLM()
    router = LocalModelRouter(intent_engine=intent_engine, local_llm=local_llm)

    # 2. Enroll user's voice profile with explicit consent
    b64_sample = _make_audio_sample()
    enroll_req = SpeakerEnrollmentRequest(
        user_id="user-primary",
        speaker_name="Vaibhav",
        consent_token="user_primary_signed_biometric_consent_token_2026",
        audio_samples_pcm_base64=[b64_sample],
        accent="indian_english",
    )
    profile = enrollment_mgr.enroll_voice(enroll_req)
    assert profile.is_verified is True

    # 3. Process agentic query through local router
    query = "Analyze the repo architecture and formulate a refactoring plan"
    response_text, route, telemetry = await router.route_and_execute(query)
    assert route == "LOCAL_QUANTIZED_LLM"
    assert len(response_text) > 0

    # 4. Synthesize response using enrolled personalized voice profile
    synth_req = VoiceSynthesisRequest(
        text=response_text,
        speaker_profile=profile,
        language="hinglish",
        accent="indian_english",
    )
    synth_res = tts.synthesize_speech(synth_req)
    assert len(synth_res.audio_bytes) > 0
    assert synth_res.accent_applied == "indian_english"
