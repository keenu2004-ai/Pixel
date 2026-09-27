"""Unit tests for ECAPASpeakerEncoder and speaker similarity."""

import math

import numpy as np
import pytest

from packages.contracts.models import SpeakerEnrollmentRequest
from services.voice_gateway.voice_clone.speaker_encoder import ECAPASpeakerEncoder


def _generate_synthetic_speech_sample(
    freq: float = 220.0, duration: float = 1.5, sample_rate: int = 16000
) -> bytes:
    """Helper to generate a clean synthetic voiced PCM audio buffer."""
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False, dtype=np.float32)
    # Fundamental + harmonics with speech-like envelope
    sig = (np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * freq * 2 * t)) * 0.5
    # Add slight background noise for realistic SNR
    noise = np.random.normal(0, 0.01, num_samples).astype(np.float32)
    waveform = ((sig + noise) * 32767).astype(np.int16)
    return waveform.tobytes()


def test_embedding_extraction_and_unit_norm() -> None:
    encoder = ECAPASpeakerEncoder(embedding_dim=192)
    sample = _generate_synthetic_speech_sample(freq=200.0, duration=1.5)

    embedding = encoder.encode_embedding([sample])
    assert len(embedding) == 192

    norm = math.sqrt(sum(x**2 for x in embedding))
    assert norm == pytest.approx(1.0, 0.001)


def test_cosine_similarity_calculation() -> None:
    encoder = ECAPASpeakerEncoder(embedding_dim=192)

    vec_a = [1.0, 0.0, 0.0] + [0.0] * 189
    vec_b = [1.0, 0.0, 0.0] + [0.0] * 189
    assert encoder.compute_similarity(vec_a, vec_b) == pytest.approx(1.0, 0.001)

    vec_orthogonal = [0.0, 1.0, 0.0] + [0.0] * 189
    assert encoder.compute_similarity(vec_a, vec_orthogonal) == pytest.approx(0.0, 0.001)


def test_speaker_enrollment_and_verification() -> None:
    import base64

    encoder = ECAPASpeakerEncoder()

    sample_enrolled = _generate_synthetic_speech_sample(freq=180.0, duration=2.0)
    b64_sample = base64.b64encode(sample_enrolled).decode()

    req = SpeakerEnrollmentRequest(
        user_id="user-42",
        speaker_name="Speaker 42",
        consent_token="consent_valid_authorization_signature_42",
        audio_samples_pcm_base64=[b64_sample],
        accent="indian_english",
    )

    profile = encoder.enroll_speaker(req)
    assert profile.speaker_name == "Speaker 42"
    assert profile.is_verified is True

    # Same speaker verifies successfully
    res_match = encoder.verify_speaker(sample_enrolled, profile, threshold=0.85)
    assert res_match.is_match is True
    assert res_match.similarity_score > 0.85

    # Different acoustic signature yields different embedding
    sample_diff = _generate_synthetic_speech_sample(freq=350.0, duration=2.0)
    emb_diff = encoder.encode_embedding([sample_diff])
    sim = encoder.compute_similarity(emb_diff, profile.embedding_vector)
    assert sim < 0.85


def test_rejection_of_invalid_audio_quality() -> None:
    encoder = ECAPASpeakerEncoder(min_duration_seconds=1.0)

    # 1. Too short duration
    short_sample = _generate_synthetic_speech_sample(duration=0.2)
    with pytest.raises(ValueError, match="duration"):
        encoder.encode_embedding([short_sample])

    # 2. Complete silence (zero energy)
    silence = (np.zeros(16000, dtype=np.int16)).tobytes()
    with pytest.raises(ValueError, match="silence"):
        encoder.encode_embedding([silence])
