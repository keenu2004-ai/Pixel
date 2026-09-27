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
    manufacturer: str = Field(
        default="Android", description="Device manufacturer (e.g. Google, Samsung)"
    )
    model: str = Field(default="Pixel", description="Device model name")
    os_version: str = Field(default="Android 14 (API 34)", description="Android OS version string")
    api_level: int = Field(default=34, ge=21, description="Android SDK API level")
    battery_level: int = Field(default=100, ge=0, le=100, description="Battery percentage")
    is_charging: bool = Field(default=False, description="Whether device is connected to power")
    is_screen_on: bool = Field(default=True, description="Whether display is active")
    is_default_assistant: bool = Field(
        default=False, description="Whether PIXEL holds ROLE_ASSISTANT"
    )
    has_mic_permission: bool = Field(default=True, description="Whether RECORD_AUDIO is granted")
    has_notification_permission: bool = Field(
        default=True, description="Whether POST_NOTIFICATIONS is granted"
    )


class MobileRegistrationRequest(BaseModel):
    """Registration handshake payload sent by Android client upon connection."""

    device_id: str = Field(..., description="Unique client device ID")
    auth_token: str = Field(..., description="Shared or provisioned bearer authorization token")
    device_metadata: MobileDeviceMetadata = Field(..., description="Hardware and permission state")
    preferred_language: str = Field(
        default="en", description="Default language code (en, hi, hinglish)"
    )
    timestamp: datetime = Field(default_factory=_utc_now)


class MobileRegistrationResponse(BaseModel):
    """Response returned by PIXEL Voice Gateway to registering mobile client."""

    success: bool = Field(..., description="Whether registration and authentication succeeded")
    session_id: str = Field(default_factory=_gen_id, description="Allocated gateway session ID")
    websocket_url: str = Field(
        default="/ws/voice", description="Streaming audio WebSocket endpoint"
    )
    heartbeat_interval_seconds: int = Field(default=30, ge=5, le=300)
    error_message: str | None = Field(default=None, description="Reason if registration rejected")
    server_time: datetime = Field(default_factory=_utc_now)


class MobileVoicePacket(BaseModel):
    """Audio or control packet exchanged between Android and PIXEL Gateway."""

    packet_id: str = Field(default_factory=_gen_id)
    session_id: str = Field(..., description="Active session ID")
    event_type: str = Field(
        default="audio_frame", description="audio_frame, wake_detected, barge_in, or tts_playback"
    )
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
    biometric_authenticated: bool = Field(
        default=False, description="Whether verified via BiometricPrompt"
    )
    timestamp: datetime = Field(default_factory=_utc_now)


# ============================================================================
# Android Native Action Contracts
# ============================================================================


class AndroidActionType(StrEnum):
    """Supported Android native intent/service action categories."""

    CALL = "CALL"
    SMS = "SMS"
    ALARM = "ALARM"
    TIMER = "TIMER"
    MEDIA_CONTROL = "MEDIA_CONTROL"
    NOTIFICATION = "NOTIFICATION"
    CALENDAR = "CALENDAR"
    LAUNCH_APP = "LAUNCH_APP"
    DEVICE_SETTING = "DEVICE_SETTING"


class AndroidContact(BaseModel):
    """Resolved contact entity from Android Contact Provider."""

    contact_id: str = Field(default_factory=_gen_id)
    display_name: str
    phone_number: str
    is_primary: bool = True


class AndroidAlarmSpec(BaseModel):
    """Specification for setting an Android alarm."""

    hour: int = Field(..., ge=0, le=23)
    minutes: int = Field(..., ge=0, le=59)
    message: str = Field(default="PIXEL Alarm")
    days_of_week: list[int] = Field(
        default_factory=list, description="1=Sunday, 2=Monday, ..., 7=Saturday"
    )
    skip_ui: bool = True
    vibrate: bool = True


class AndroidTimerSpec(BaseModel):
    """Specification for setting an Android countdown timer."""

    duration_seconds: int = Field(..., gt=0)
    label: str = Field(default="PIXEL Timer")
    skip_ui: bool = True


class AndroidMediaCommand(StrEnum):
    """Supported Android media session commands."""

    PLAY = "PLAY"
    PAUSE = "PAUSE"
    STOP = "STOP"
    NEXT = "NEXT"
    PREVIOUS = "PREVIOUS"
    VOLUME_UP = "VOLUME_UP"
    VOLUME_DOWN = "VOLUME_DOWN"
    SET_VOLUME = "SET_VOLUME"
    MUTE = "MUTE"


class AndroidCalendarEvent(BaseModel):
    """Calendar event payload for Android CalendarProvider."""

    event_id: str = Field(default_factory=_gen_id)
    title: str
    start_time_iso: str
    end_time_iso: str
    location: str = ""
    description: str = ""
    all_day: bool = False


class AndroidActionPayload(BaseModel):
    """Standardized action payload dispatched to Android client or simulated runtime."""

    action_id: str = Field(default_factory=_gen_id)
    action_type: AndroidActionType
    target_package: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


class AndroidActionResult(BaseModel):
    """Verification and execution status returned from Android Action Handler."""

    action_id: str
    action_type: AndroidActionType
    success: bool
    state_verified: bool = False
    error_message: str | None = None
    result_data: dict[str, Any] = Field(default_factory=dict)
    executed_at: datetime = Field(default_factory=_utc_now)
