"""Unit tests for VoiceEnrollmentManager and consent lifecycle."""

import base64

import numpy as np
import pytest

from packages.contracts.models import SpeakerEnrollmentRequest
from services.voice_gateway.voice_clone.enrollment import VoiceEnrollmentManager


def _make_audio_sample() -> str:
    num_samples = 24000
    t = np.linspace(0, 1.5, num_samples, endpoint=False, dtype=np.float32)
    sig = np.sin(2 * np.pi * 220 * t) * 0.5
    noise = np.random.normal(0, 0.01, num_samples).astype(np.float32)
    waveform = ((sig + noise) * 32767).astype(np.int16)
    return base64.b64encode(waveform.tobytes()).decode()


def test_enrollment_lifecycle_and_consent_enforcement() -> None:
    manager = VoiceEnrollmentManager()
    b64_sample = _make_audio_sample()

    # 1. Reject without consent token
    bad_req = SpeakerEnrollmentRequest(
        user_id="user-1",
        speaker_name="Voice 1",
        consent_token="",  # Missing
        audio_samples_pcm_base64=[b64_sample],
    )
    with pytest.raises(PermissionError, match="consent token"):
        manager.enroll_voice(bad_req)

    # 2. Enroll with valid consent token
    valid_req = SpeakerEnrollmentRequest(
        user_id="user-1",
        speaker_name="Voice 1",
        consent_token="user_1_explicit_biometric_consent_token_2026",
        audio_samples_pcm_base64=[b64_sample],
        accent="indian_english",
    )
    profile = manager.enroll_voice(valid_req)
    assert profile.speaker_name == "Voice 1"
    assert len(profile.embedding_vector) == 192

    # 3. Retrieve and list profiles
    retrieved = manager.get_profile(profile.speaker_id)
    assert retrieved is not None
    assert retrieved.speaker_id == profile.speaker_id

    user_profiles = manager.list_user_profiles("user-1")
    assert len(user_profiles) == 1
    assert user_profiles[0].speaker_id == profile.speaker_id


def test_profile_deletion_and_reset() -> None:
    manager = VoiceEnrollmentManager()
    b64_sample = _make_audio_sample()

    req = SpeakerEnrollmentRequest(
        user_id="user-1",
        speaker_name="Voice to delete",
        consent_token="consent_token_for_deletion_test_12345",
        audio_samples_pcm_base64=[b64_sample],
    )
    profile = manager.enroll_voice(req)

    # Cross-user deletion attempt fails
    with pytest.raises(PermissionError, match="another user"):
        manager.delete_profile(profile.speaker_id, user_id="unauthorized-user-2")

    # Authorized deletion succeeds
    assert manager.delete_profile(profile.speaker_id, user_id="user-1") is True
    assert manager.get_profile(profile.speaker_id) is None
    assert len(manager.list_user_profiles("user-1")) == 0
