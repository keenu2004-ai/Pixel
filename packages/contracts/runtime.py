"""PIXEL — Phase 13 Real-World Runtime, Voice Streaming & Multi-Device Execution Contracts.

Defines schemas and models for:
1. Streaming audio, VAD, Wake-Word, STT, and TTS with Barge-In.
2. Controlled OS, Filesystem, Terminal, and Browser tool executions.
3. Multi-device mesh node registry and seamless context handoffs.
4. End-to-end request tracing metrics and observability.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# 1. Voice Streaming & Interruption (Barge-In) Contracts
# ============================================================================


class AudioStreamConfig(BaseModel):
    """Audio configuration for microphone and streaming pipelines."""

    sample_rate: int = 16000
    channels: int = 1
    sample_width_bytes: int = 2  # 16-bit PCM
    chunk_size_samples: int = 512  # ~32ms chunks
    encoding: str = "pcm_s16le"


class WakeDetectionResult(BaseModel):
    """Wake-word detection event."""

    detection_id: str = Field(default_factory=_gen_id)
    wake_phrase: str  # e.g., "hey_pixel", "pixel_sun", "o_pixel"
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    detection_latency_ms: float = 0.0
    detected_at: str = Field(default_factory=_utc_now_iso)


class VADSegment(BaseModel):
    """Voice Activity Detection speech boundary segment."""

    segment_id: str = Field(default_factory=_gen_id)
    speech_start_ms: float
    speech_end_ms: float
    is_speech: bool = True
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    audio_bytes_length: int = 0


class STTTranscriptResult(BaseModel):
    """Speech-to-Text transcript result with language and streaming flags."""

    transcript_id: str = Field(default_factory=_gen_id)
    text: str
    language: str = "en"  # en, hi, hinglish
    is_final: bool = True
    confidence: float = 0.95
    latency_ms: float = 0.0
    provider: str = "whisper_hybrid"
    words: list[dict[str, Any]] = Field(default_factory=list)


class TTSStreamChunk(BaseModel):
    """Streaming audio chunk emitted by TTS engine."""

    chunk_id: str = Field(default_factory=_gen_id)
    session_id: str
    sequence_number: int = 0
    pcm_bytes_base64: str = ""
    sample_rate: int = 24000
    is_final_chunk: bool = False
    duration_ms: float = 0.0


class BargeInEvent(BaseModel):
    """User speech interruption event triggering instant audio cancellation."""

    barge_in_id: str = Field(default_factory=_gen_id)
    session_id: str
    interrupted_tts_sequence: int = 0
    speech_detected_ms: float = 0.0
    cancelled_tasks: list[str] = Field(default_factory=list)
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class VoiceProfileContext(BaseModel):
    """Personalized speaker identity and voice conditioning embedding context."""

    user_id: str
    speaker_name: str
    consent_verified: bool = True
    voice_embedding_dim: int = 256
    pitch_adjustment: float = 1.0
    speed_factor: float = 1.0


# ============================================================================
# 2. Controlled OS, Filesystem, Terminal & Browser Tool Contracts
# ============================================================================


class FilesystemOperationResult(BaseModel):
    """Result of safe sandboxed filesystem operation."""

    operation: str  # read, write, list, delete, stat
    target_path: str
    success: bool
    size_bytes: int = 0
    content: str | None = None
    files: list[str] = Field(default_factory=list)
    error: str | None = None
    state_verified: bool = True


class TerminalCommandResult(BaseModel):
    """Result of policy-gated and secret-stripped terminal execution."""

    command_id: str = Field(default_factory=_gen_id)
    command_executed: str
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0.0
    secrets_redacted_count: int = 0
    timed_out: bool = False


class BrowserActionResult(BaseModel):
    """Result of controlled browser automation action."""

    action_id: str = Field(default_factory=_gen_id)
    action_type: str  # navigate, click, type, get_text, screenshot
    target_url: str = ""
    success: bool = True
    page_title: str = ""
    extracted_text: str | None = None
    screenshot_base64: str | None = None
    error: str | None = None


# ============================================================================
# 3. Multi-Device Mesh & Context Handoff Contracts
# ============================================================================


class MultiDeviceNodeRole(StrEnum):
    """Device node roles within the PIXEL multi-device mesh."""

    PHONE = "PHONE"
    DESKTOP = "DESKTOP"
    SERVER = "SERVER"
    SATELLITE = "SATELLITE"


class CrossDeviceHandoffState(StrEnum):
    """State machine for cross-device context and task handoffs."""

    INITIATED = "INITIATED"
    ROUTED = "ROUTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"


class CrossDeviceHandoffContext(BaseModel):
    """Cross-device contextual payload transferring task state seamlessly."""

    handoff_id: str = Field(default_factory=_gen_id)
    origin_device_id: str
    origin_role: MultiDeviceNodeRole
    target_device_id: str
    target_role: MultiDeviceNodeRole
    task_id: str
    session_id: str
    user_id: str
    serialized_context: dict[str, Any] = Field(default_factory=dict)
    state: CrossDeviceHandoffState = CrossDeviceHandoffState.INITIATED
    created_at: str = Field(default_factory=_utc_now_iso)


class CrossDeviceHandoffResult(BaseModel):
    """Handoff execution result returned to coordinating node."""

    handoff_id: str
    success: bool
    response_device_id: str
    response_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    completed_at: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 4. End-to-End Observability & Tracing Metrics
# ============================================================================


class VoiceToResponseTrace(BaseModel):
    """End-to-end latency and telemetry record for a complete voice request."""

    trace_id: str = Field(default_factory=_gen_id)
    session_id: str
    user_id: str
    wake_latency_ms: float = 0.0
    vad_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    intent_routing_latency_ms: float = 0.0
    agent_planning_latency_ms: float = 0.0
    policy_evaluation_latency_ms: float = 0.0
    tool_execution_latency_ms: float = 0.0
    verification_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    total_voice_to_action_latency_ms: float = 0.0
    total_voice_to_response_latency_ms: float = 0.0
    device_id: str = "pixel-local"
    model_used: str = "deterministic"
    state_verified: bool = True
    status: str = "SUCCESS"
