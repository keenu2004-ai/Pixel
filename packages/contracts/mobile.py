"""Android & Mobile Device Runtime Contracts.

Defines schemas for mobile client registration, device telemetry,
assistant lifecycle states, audio transport packets, and mobile approval cards.
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


class MobileAssistantState(StrEnum):
    """Lifecycle state of the Android Assistant client."""
    UNINITIALIZED = "UNINITIALIZED"
    INITIALIZING = "INITIALIZING"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    READY = "READY"
    LISTENING = "LISTENING"
    WAKE_DETECTED = "WAKE_DETECTED"
    PROCESSING = "PROCESSING"
    SPEAKING = "SPEAKING"
    INTERRUPTED = "INTERRUPTED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    DISCONNECTED = "DISCONNECTED"
    RECONNECTING = "RECONNECTING"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


class MobileDeviceMetadata(BaseModel):
    """Telemetry and hardware profile of connected Android device."""
    device_id: str = Field(..., description="Unique hardware or app instance ID")
    manufacturer: str = Field(default="Android", description="Device manufacturer (e.g. Google, Samsung)")
    model: str = Field(default="Pixel", description="Device model name")
    os_version: str = Field(default="Android 14 (API 34)", description="Android OS version string")
    api_level: int = Field(default=34, ge=21, description="Android SDK API level")
    battery_level: int = Field(default=100, ge=0, le=100, description="Battery percentage")
    is_charging: bool = Field(default=False, description="Whether device is connected to power")
    is_screen_on: bool = Field(default=True, description="Whether display is active")
    is_default_assistant: bool = Field(default=False, description="Whether PIXEL holds ROLE_ASSISTANT")
    has_mic_permission: bool = Field(default=True, description="Whether RECORD_AUDIO is granted")
    has_notification_permission: bool = Field(default=True, description="Whether POST_NOTIFICATIONS is granted")


class MobileRegistrationRequest(BaseModel):
    """Registration handshake payload sent by Android client upon connection."""
    device_id: str = Field(..., description="Unique client device ID")
    auth_token: str = Field(..., description="Shared or provisioned bearer authorization token")
    device_metadata: MobileDeviceMetadata = Field(..., description="Hardware and permission state")
    preferred_language: str = Field(default="en", description="Default language code (en, hi, hinglish)")
    timestamp: datetime = Field(default_factory=_utc_now)


class MobileRegistrationResponse(BaseModel):
    """Response returned by PIXEL Voice Gateway to registering mobile client."""
    success: bool = Field(..., description="Whether registration and authentication succeeded")
    session_id: str = Field(default_factory=_gen_id, description="Allocated gateway session ID")
    websocket_url: str = Field(default="/ws/voice", description="Streaming audio WebSocket endpoint")
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300)
    error_message: str | None = Field(default=None, description="Reason if registration rejected")
    server_time: datetime = Field(default_factory=_utc_now)


class MobileVoicePacket(BaseModel):
    """Audio or control packet exchanged between Android and PIXEL Gateway."""
    packet_id: str = Field(default_factory=_gen_id)
    session_id: str = Field(..., description="Active session ID")
    event_type: str = Field(default="audio_frame", description="audio_frame, wake_detected, barge_in, or tts_playback")
    pcm_base64: str | None = Field(default=None, description="Base64 encoded 16kHz 16-bit mono PCM")
    sample_rate: int = Field(default=16000, ge=8000, le=48000)
    timestamp_ms: int = Field(default=0, ge=0)
    is_final_chunk: bool = Field(default=False)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MobileApprovalRequest(BaseModel):
    """Card presented to Android user for biometric/explicit approval of high-impact action."""
    approval_id: str = Field(..., description="Approval transaction identifier")
    task_id: str = Field(..., description="Backend agent task ID")
    tool_name: str = Field(..., description="Action to be approved")
    risk_class: str = Field(..., description="Risk tier (e.g. HIGH_IMPACT)")
    reason: str = Field(..., description="Explanation why confirmation is necessary")
    arguments_summary: dict[str, Any] = Field(default_factory=dict)
    confirmation_token: str = Field(..., description="HMAC confirmation token")
    created_at: datetime = Field(default_factory=_utc_now)


class MobileApprovalResponse(BaseModel):
    """User decision returned from Android client after biometric or PIN authorization."""
    approval_id: str = Field(..., description="Matching approval request ID")
    task_id: str = Field(..., description="Task ID")
    confirmation_token: str = Field(..., description="Signed confirmation token")
    user_approved: bool = Field(..., description="True if confirmed, False if dismissed")
    biometric_authenticated: bool = Field(default=False, description="Whether verified via BiometricPrompt")
    timestamp: datetime = Field(default_factory=_utc_now)
