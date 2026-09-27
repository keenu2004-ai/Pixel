"""Voice & Runtime Event Contracts.

Defines typed, serializable data structures for the L0-L10 perception and interaction pipeline.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _generate_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class VoiceState(StrEnum):
    """The 11 operational UI and cognitive states for PIXEL."""

    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    WAITING_CONFIRMATION = "WAITING_CONFIRMATION"
    SECURE_ACTION_PENDING = "SECURE_ACTION_PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    OFFLINE = "OFFLINE"


class BaseEvent(BaseModel):
    """Base event contract with standard correlation, session, and tracing IDs."""

    event_id: str = Field(default_factory=_generate_id, description="Unique event identifier")
    session_id: str = Field(..., description="Active user session identifier")
    correlation_id: str = Field(
        default_factory=_generate_id, description="Correlation ID spanning causality chain"
    )
    trace_id: str = Field(
        default_factory=_generate_id, description="Distributed OpenTelemetry trace ID"
    )
    timestamp: datetime = Field(
        default_factory=_utc_now, description="Event creation timestamp in UTC"
    )


class AudioFrame(BaseModel):
    """16kHz 16-bit mono audio chunk for L0 streaming."""

    sample_rate: int = Field(
        default=16000, ge=8000, le=48000, description="Audio sample rate in Hz"
    )
    channels: int = Field(default=1, ge=1, le=2, description="Number of audio channels")
    pcm_data: bytes = Field(..., description="Raw PCM audio byte buffer")
    timestamp_ms: int = Field(..., ge=0, description="Audio capture timestamp in milliseconds")


class VADState(StrEnum):
    """Voice Activity Detection state transitions."""

    SPEECH_START = "SPEECH_START"
    SPEECH_CONTINUING = "SPEECH_CONTINUING"
    SPEECH_END = "SPEECH_END"
    SILENCE = "SILENCE"


class VADEvent(BaseEvent):
    """Event emitted by L0/L1 Voice Activity Detection."""

    state: VADState = Field(..., description="VAD state classification")
    speech_probability: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence probability of speech"
    )
    energy_level_db: float = Field(default=-20.0, description="Audio energy level in decibels")


class WakeEvent(BaseEvent):
    """Event emitted when a designated wake phrase is detected."""

    phrase: str = Field(
        ..., description="Detected activation phrase (e.g. 'Hey Pixel', 'Oye Pixel')"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Detection confidence score")
    offset_ms: int = Field(default=0, ge=0, description="Audio buffer offset in milliseconds")


class TranscriptEvent(BaseEvent):
    """Streaming or finalized speech-to-text transcript hypothesis."""

    text: str = Field(..., description="Transcribed text content")
    is_final: bool = Field(default=False, description="Whether this is the final hypothesis")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    language: str = Field(
        default="en", description="Detected language code (e.g. en, hi, hi-Latn, hinglish)"
    )
    duration_ms: int | None = Field(
        default=None, ge=0, description="Speech duration in milliseconds"
    )
    provider: str = Field(default="unknown", description="STT engine provider identifier")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional provider metadata"
    )


class StateChangeEvent(BaseEvent):
    """Event emitted when the system voice state transitions."""

    previous_state: VoiceState = Field(..., description="Previous operating state")
    current_state: VoiceState = Field(..., description="New operating state")
    reason: str = Field(default="", description="Trigger explanation for state transition")
