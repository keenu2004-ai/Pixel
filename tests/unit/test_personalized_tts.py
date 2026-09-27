"""Unit tests for PersonalizedTTSProvider and Indic speech synthesis."""

from datetime import UTC, datetime

import pytest

from packages.contracts.models import SpeakerProfile, VoiceSynthesisRequest
from services.voice_gateway.voice_clone.personalized_tts import PersonalizedTTSProvider


def test_personalized_tts_synthesis() -> None:
    tts = PersonalizedTTSProvider(sample_rate=24000)
    now = datetime.now(UTC)

    profile = SpeakerProfile(
        user_id="user-1",
        speaker_name="Vaibhav",
        embedding_vector=[0.05] * 192,
        embedding_dim=192,
        accent="indian_english",
        created_at=now,
        updated_at=now,
    )

    req = VoiceSynthesisRequest(
        text="Pixel, open my project and run the unit tests.",
        speaker_profile=profile,
        language="en",
        accent="indian_english",
    )

    res = tts.synthesize_speech(req)
    assert len(res.audio_bytes) > 0
    assert res.sample_rate == 24000
    assert res.duration_seconds > 0.4
    assert res.accent_applied == "indian_english"


def test_hinglish_and_hindi_synthesis() -> None:
    tts = PersonalizedTTSProvider()

    # Hinglish query
    req_hinglish = VoiceSynthesisRequest(
        text="Pixel, kal subah 7 baje alarm laga dena aur code build check karo.",
        language="hinglish",
        accent="indian_english",
    )
    res_hinglish = tts.synthesize_speech(req_hinglish)
    assert len(res_hinglish.audio_bytes) > 0

    # Devanagari Hindi query
    req_hindi = VoiceSynthesisRequest(
        text="नमस्ते पिक्सल, आज का मौसम कैसा है?",
        language="hi",
        accent="hindi_prosody",
    )
    res_hindi = tts.synthesize_speech(req_hindi)
    assert len(res_hindi.audio_bytes) > 0


@pytest.mark.asyncio
async def test_personalized_tts_streaming() -> None:
    tts = PersonalizedTTSProvider()
    chunks: list[bytes] = []

    async for chunk in tts.synthesize_stream("Testing real-time streaming audio generation."):
        chunks.append(chunk)

    assert len(chunks) > 0
    total_bytes = sum(len(c) for c in chunks)
    assert total_bytes > 0
