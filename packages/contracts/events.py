"""Voice & Runtime Event Contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field


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


class AudioFrame(BaseModel):
    """16kHz 16-bit mono audio chunk."""
    sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    channels: int = Field(default=1, description="Number of audio channels")
    pcm_data: bytes = Field(..., description="Raw PCM audio byte buffer")
    timestamp_ms: int = Field(..., description="Audio capture timestamp in milliseconds")


class TranscriptEvent(BaseModel):
    """Streaming or finalized speech-to-text transcript hypothesis."""
    text: str = Field(..., description="Transcribed text content")
    is_final: bool = Field(default=False, description="Whether this is the final hypothesis")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    language: str = Field(default="en", description="Detected language code (e.g. en, hi, hinglish)")
    duration_ms: int | None = Field(default=None, description="Speech duration in milliseconds")
