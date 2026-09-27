"""Unit tests for Phase 8 models contracts and data structures."""

from datetime import UTC, datetime

from packages.contracts.models import (
    LocalLLMRequest,
    LocalLLMResponse,
    ModelFamily,
    ModelLifecycleState,
    ModelMetadata,
    QuantizationType,
    SpeakerEnrollmentRequest,
    SpeakerProfile,
    SpeakerVerificationResult,
    VoiceSynthesisRequest,
    VoiceSynthesisResult,
)


def test_model_enums() -> None:
    assert ModelLifecycleState.UNLOADED == "UNLOADED"
    assert ModelLifecycleState.READY == "READY"
    assert ModelLifecycleState.INFERENCING == "INFERENCING"

    assert QuantizationType.INT4 == "INT4"
    assert QuantizationType.Q4_K_M == "Q4_K_M"
    assert QuantizationType.GGUF == "GGUF"

    assert ModelFamily.QWEN == "QWEN"
    assert ModelFamily.LLAMA == "LLAMA"
    assert ModelFamily.KOKORO_TTS == "KOKORO_TTS"
    assert ModelFamily.ECAPA_SPEAKER == "ECAPA_SPEAKER"


def test_model_metadata_contract() -> None:
    meta = ModelMetadata(
        model_id="llama-3.2-3b-q4",
        model_name="Llama 3.2 3B Instruct (4-bit)",
        family=ModelFamily.LLAMA,
        quantization=QuantizationType.Q4_K_M,
        file_path="data/models/llm/llama-3.2-3b.gguf",
        sha256_hash="abc" * 21 + "a",
        context_length=4096,
        memory_required_mb=2048,
    )
    assert meta.model_id == "llama-3.2-3b-q4"
    assert meta.quantization == QuantizationType.Q4_K_M
    assert meta.memory_required_mb == 2048


def test_speaker_contracts() -> None:
    now = datetime.now(UTC)
    req = SpeakerEnrollmentRequest(
        user_id="user-123",
        speaker_name="Vaibhav",
        consent_token="consent_token_signature_xyz_12345",
        audio_samples_pcm_base64=["YWJjZGVmZ2hpams="],
    )
    assert req.user_id == "user-123"
    assert req.accent == "indian_english"

    prof = SpeakerProfile(
        user_id="user-123",
        speaker_name="Vaibhav",
        embedding_vector=[0.1] * 192,
        embedding_dim=192,
        created_at=now,
        updated_at=now,
    )
    assert len(prof.embedding_vector) == 192

    ver = SpeakerVerificationResult(
        is_match=True,
        similarity_score=0.92,
        threshold=0.75,
        speaker_id=prof.speaker_id,
        confidence=0.96,
    )
    assert ver.is_match is True
    assert ver.similarity_score == 0.92


def test_synthesis_contracts() -> None:
    req = VoiceSynthesisRequest(
        text="Pixel, open VS Code aur backend run karo",
        language="hinglish",
        accent="indian_english",
    )
    assert req.language == "hinglish"

    res = VoiceSynthesisResult(
        audio_bytes=b"\x00\x00" * 100,
        sample_rate=24000,
        duration_seconds=1.2,
        phoneme_count=25,
        accent_applied="indian_english",
        latency_ms=12.5,
    )
    assert len(res.audio_bytes) == 200
    assert res.duration_seconds == 1.2


def test_local_llm_contracts() -> None:
    req = LocalLLMRequest(
        prompt="List open files",
        system_prompt="You are PIXEL.",
        temperature=0.5,
    )
    assert req.temperature == 0.5

    resp = LocalLLMResponse(
        content="Here are the open files.",
        tool_calls=[{"name": "list_files", "arguments": {}}],
        tokens_generated=10,
        prompt_tokens=5,
        total_tokens=15,
        latency_ms=45.0,
        model_id="qwen2.5-coder-7b",
        quantization=QuantizationType.INT4,
    )
    assert resp.total_tokens == 15
    assert len(resp.tool_calls) == 1
