"""Personalized Voice Cloning & Local Model Contracts.

Defines schemas and enums for speaker embedding vectors, authorized voice
enrollment, Indian accent adaptation, 4-bit quantized local LLM execution,
and model lifecycle states.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class ModelLifecycleState(StrEnum):
    """Lifecycle state of an on-device local neural model."""

    UNLOADED = "UNLOADED"
    LOADING = "LOADING"
    READY = "READY"
    INFERENCING = "INFERENCING"
    UNLOADING = "UNLOADING"
    ERROR = "ERROR"


class QuantizationType(StrEnum):
    """Precision and quantization format for local model weights."""

    NONE = "NONE"
    FP16 = "FP16"
    INT8 = "INT8"
    INT4 = "INT4"
    Q4_K_M = "Q4_K_M"
    Q4_0 = "Q4_0"
    AWQ = "AWQ"
    GGUF = "GGUF"


class ModelFamily(StrEnum):
    """Architectural neural model family."""

    QWEN = "QWEN"
    LLAMA = "LLAMA"
    MISTRAL = "MISTRAL"
    KOKORO_TTS = "KOKORO_TTS"
    F5_TTS = "F5_TTS"
    ECAPA_SPEAKER = "ECAPA_SPEAKER"
    CUSTOM = "CUSTOM"


class ModelMetadata(BaseModel):
    """Detailed specifications and hardware requirements of a local model."""

    model_id: str = Field(..., description="Unique model identifier")
    model_name: str = Field(..., description="Display name of model")
    family: ModelFamily = Field(..., description="Model architecture family")
    version: str = Field(default="1.0.0")
    quantization: QuantizationType = Field(default=QuantizationType.INT4)
    file_path: str = Field(..., description="Filesystem location of model weights")
    sha256_hash: str = Field(..., description="Cryptographic SHA-256 integrity digest")
    context_length: int = Field(default=4096, ge=512)
    memory_required_mb: int = Field(default=1024, ge=64)
    supported_languages: list[str] = Field(default_factory=lambda: ["en", "hi", "hinglish"])


class SpeakerEnrollmentRequest(BaseModel):
    """Authorized speaker enrollment payload containing voice samples and explicit consent."""

    enrollment_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(..., description="User identity owning the voice profile")
    speaker_name: str = Field(..., description="Label/alias for the enrolled speaker")
    consent_token: str = Field(
        ..., description="Signed consent token authorizing biometric voice modeling"
    )
    audio_samples_pcm_base64: list[str] = Field(
        ..., min_length=1, description="Base64 encoded 16kHz PCM audio samples"
    )
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    language: str = Field(default="en")
    accent: str = Field(default="indian_english")
    created_at: datetime = Field(default_factory=_utc_now)


class SpeakerProfile(BaseModel):
    """Persistent mathematical speaker identity embedding and acoustic metadata."""

    speaker_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(...)
    speaker_name: str = Field(...)
    embedding_vector: list[float] = Field(..., description="L2-normalized speaker embedding vector")
    embedding_dim: int = Field(default=192, ge=64, le=1024)
    model_version: str = Field(default="ecapa-tdnn-v1")
    accent: str = Field(default="indian_english")
    quality_score: float = Field(default=1.0, ge=0.0, le=1.0)
    is_verified: bool = Field(default=True)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class SpeakerVerificationResult(BaseModel):
    """Result of comparing an incoming audio sample against an enrolled speaker profile."""

    is_match: bool = Field(...)
    similarity_score: float = Field(..., ge=-1.0, le=1.0, description="Cosine similarity score")
    threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    speaker_id: str = Field(...)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class VoiceSynthesisRequest(BaseModel):
    """Request payload for personalized or cloned speech synthesis."""

    text: str = Field(..., min_length=1)
    speaker_id: str | None = Field(default=None)
    speaker_profile: SpeakerProfile | None = Field(default=None)
    language: str = Field(default="en", description="en, hi, hi-Latn, or hinglish")
    accent: str = Field(default="indian_english")
    speaking_rate: float = Field(default=1.0, ge=0.5, le=2.0)
    pitch: float = Field(default=1.0, ge=0.5, le=2.0)


class VoiceSynthesisResult(BaseModel):
    """Generated synthetic speech waveform and execution telemetry."""

    audio_bytes: bytes = Field(..., description="Synthesized 16-bit PCM audio bytes")
    sample_rate: int = Field(default=24000, ge=8000, le=48000)
    duration_seconds: float = Field(..., ge=0.0)
    phoneme_count: int = Field(default=0, ge=0)
    accent_applied: str = Field(default="indian_english")
    latency_ms: float = Field(default=0.0, ge=0.0)


class LocalLLMRequest(BaseModel):
    """Inference prompt request dispatched to local quantized model."""

    prompt: str = Field(...)
    system_prompt: str | None = Field(default=None)
    messages: list[dict[str, Any]] = Field(default_factory=list)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=512, ge=1, le=8192)
    stop_sequences: list[str] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)


class LocalLLMResponse(BaseModel):
    """Generated response text, tool call plans, and performance metrics."""

    content: str = Field(default="")
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tokens_generated: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    model_id: str = Field(...)
    quantization: QuantizationType = Field(default=QuantizationType.INT4)
