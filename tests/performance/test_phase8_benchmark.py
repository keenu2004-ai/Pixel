"""Performance benchmarks for Phase 8 Voice Cloning and Local Models."""

import time
from datetime import UTC, datetime

import numpy as np
import pytest

from packages.contracts.models import (
    LocalLLMRequest,
    SpeakerProfile,
    VoiceSynthesisRequest,
)
from services.agent_runtime.local_llm.provider import QuantizedLocalLLM
from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter
from services.voice_gateway.voice_clone.personalized_tts import PersonalizedTTSProvider
from services.voice_gateway.voice_clone.speaker_encoder import ECAPASpeakerEncoder


def _make_audio_sample() -> bytes:
    num_samples = 24000
    t = np.linspace(0, 1.5, num_samples, endpoint=False, dtype=np.float32)
    sig = np.sin(2 * np.pi * 220 * t) * 0.5
    noise = np.random.normal(0, 0.01, num_samples).astype(np.float32)
    waveform = ((sig + noise) * 32767).astype(np.int16)
    return waveform.tobytes()


def test_speaker_embedding_extraction_latency_benchmark() -> None:
    encoder = ECAPASpeakerEncoder()
    sample = _make_audio_sample()

    t0 = time.perf_counter()
    embedding = encoder.encode_embedding([sample])
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert len(embedding) == 192
    assert elapsed_ms < 15.0, (
        f"Speaker embedding extraction took {elapsed_ms:.2f}ms, expected < 15ms"
    )


def test_speaker_verification_latency_benchmark() -> None:
    encoder = ECAPASpeakerEncoder()
    sample = _make_audio_sample()
    now = datetime.now(UTC)
    profile = SpeakerProfile(
        user_id="user-bench",
        speaker_name="Bench Speaker",
        embedding_vector=[0.1] * 192,
        embedding_dim=192,
        created_at=now,
        updated_at=now,
    )

    t0 = time.perf_counter()
    res = encoder.verify_speaker(sample, profile)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert res is not None
    assert elapsed_ms < 20.0, f"Speaker verification took {elapsed_ms:.2f}ms, expected < 20ms"


def test_personalized_tts_latency_benchmark() -> None:
    tts = PersonalizedTTSProvider()
    req = VoiceSynthesisRequest(
        text="Pixel, please run the test suite and report results.",
        language="en",
        accent="indian_english",
    )

    t0 = time.perf_counter()
    res = tts.synthesize_speech(req)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert len(res.audio_bytes) > 0
    assert elapsed_ms < 15.0, f"TTS synthesis took {elapsed_ms:.2f}ms, expected < 15ms"


@pytest.mark.asyncio
async def test_local_llm_inference_latency_benchmark() -> None:
    llm = QuantizedLocalLLM()
    req = LocalLLMRequest(prompt="What is the current system status?")

    t0 = time.perf_counter()
    resp = await llm.generate_response(req)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert len(resp.content) > 0
    assert elapsed_ms < 15.0, f"Local LLM inference took {elapsed_ms:.2f}ms, expected < 15ms"


@pytest.mark.asyncio
async def test_zero_regression_on_deterministic_intent_engine() -> None:
    engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())
    t0 = time.perf_counter()
    resp, packet, result = await engine.handle_transcript(
        "volume 80 percent karo", session_id="bench_sess"
    )
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert len(resp) > 0
    assert elapsed_ms < 50.0, (
        f"Deterministic intent handle took {elapsed_ms:.3f}ms, expected < 50ms"
    )
