"""Deterministic Mock Android Device Runtime for CI & Integration Testing.

Simulates Android platform VoiceInteractionService, RoleManager,
ForegroundService microphone capture, HotwordManager, and WebSocket gateway client.
"""

import base64
import logging
from typing import Any

from packages.contracts.mobile import (
    MobileApprovalRequest,
    MobileApprovalResponse,
    MobileAssistantState,
    MobileDeviceMetadata,
    MobileRegistrationRequest,
    MobileRegistrationResponse,
    MobileVoicePacket,
)
from services.voice_gateway.mobile_adapter import MobileGatewayAdapter

logger = logging.getLogger(__name__)


class MockAndroidDeviceRuntime:
    """Emulates a physical Android 14 device running PIXEL VoiceInteractionService."""

    def __init__(
        self,
        device_id: str = "mock_pixel_8_pro_001",
        model: str = "Pixel 8 Pro",
        api_level: int = 34,
        auth_token: str = "pixel_mobile_device_auth_secret_v1",
        adapter: MobileGatewayAdapter | None = None,
    ) -> None:
        self.device_id = device_id
        self.model = model
        self.api_level = api_level
        self.auth_token = auth_token
        self.adapter = adapter or MobileGatewayAdapter()

        # Android Platform State
        self.state: MobileAssistantState = MobileAssistantState.UNINITIALIZED
        self.is_default_assistant: bool = False
        self.has_mic_permission = True
        self.has_notification_permission = True
        self.is_screen_on = True
        self.battery_pct = 95
        self.is_foreground_service_running = False

        # Session & Network
        self.active_session_id: str | None = None
        self.enrolled_hotwords: list[str] = ["hey pixel", "oye pixel"]
        self.captured_packets: list[MobileVoicePacket] = []

    # -----------------------------------------------------------------------
    # 1. Lifecycle & State Machine Transitions
    # -----------------------------------------------------------------------

    def transition_to(self, new_state: MobileAssistantState, reason: str = "") -> bool:
        """Enforces valid state machine transitions."""
        valid_transitions: dict[MobileAssistantState, list[MobileAssistantState]] = {
            MobileAssistantState.UNINITIALIZED: [
                MobileAssistantState.INITIALIZING,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.INITIALIZING: [
                MobileAssistantState.PERMISSION_REQUIRED,
                MobileAssistantState.READY,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.PERMISSION_REQUIRED: [
                MobileAssistantState.READY,
                MobileAssistantState.STOPPED,
            ],
            MobileAssistantState.READY: [
                MobileAssistantState.LISTENING,
                MobileAssistantState.WAKE_DETECTED,
                MobileAssistantState.DISCONNECTED,
                MobileAssistantState.STOPPED,
            ],
            MobileAssistantState.LISTENING: [
                MobileAssistantState.WAKE_DETECTED,
                MobileAssistantState.READY,
                MobileAssistantState.DISCONNECTED,
                MobileAssistantState.STOPPED,
            ],
            MobileAssistantState.WAKE_DETECTED: [
                MobileAssistantState.PROCESSING,
                MobileAssistantState.LISTENING,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.PROCESSING: [
                MobileAssistantState.SPEAKING,
                MobileAssistantState.AWAITING_APPROVAL,
                MobileAssistantState.READY,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.SPEAKING: [
                MobileAssistantState.INTERRUPTED,
                MobileAssistantState.READY,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.INTERRUPTED: [
                MobileAssistantState.LISTENING,
                MobileAssistantState.READY,
            ],
            MobileAssistantState.AWAITING_APPROVAL: [
                MobileAssistantState.PROCESSING,
                MobileAssistantState.READY,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.DISCONNECTED: [
                MobileAssistantState.RECONNECTING,
                MobileAssistantState.READY,
                MobileAssistantState.STOPPED,
            ],
            MobileAssistantState.RECONNECTING: [
                MobileAssistantState.READY,
                MobileAssistantState.DISCONNECTED,
                MobileAssistantState.ERROR,
            ],
            MobileAssistantState.ERROR: [
                MobileAssistantState.INITIALIZING,
                MobileAssistantState.STOPPED,
            ],
            MobileAssistantState.STOPPED: [
                MobileAssistantState.INITIALIZING,
                MobileAssistantState.UNINITIALIZED,
            ],
        }

        allowed = valid_transitions.get(self.state, [])
        if new_state not in allowed:
            logger.warning("Invalid transition from %s to %s (%s)", self.state, new_state, reason)
            return False

        logger.debug("Transition: %s -> %s (%s)", self.state, new_state, reason)
        self.state = new_state
        return True

    # -----------------------------------------------------------------------
    # 2. Android RoleManager & Permissions
    # -----------------------------------------------------------------------

    def request_assistant_role(self, grant: bool = True) -> bool:
        """Simulates user accepting/denying RoleManager.ROLE_ASSISTANT intent dialog."""
        if grant:
            self.is_default_assistant = True
            logger.info("PIXEL granted ROLE_ASSISTANT by Android RoleManager")
            return True
        self.is_default_assistant = False
        return False

    def request_microphone_permission(self, grant: bool = True) -> bool:
        """Simulates runtime RECORD_AUDIO permission request."""
        self.has_mic_permission = grant
        if not grant:
            self.transition_to(
                MobileAssistantState.PERMISSION_REQUIRED, "Microphone permission denied"
            )
        elif self.state == MobileAssistantState.PERMISSION_REQUIRED:
            self.transition_to(MobileAssistantState.READY, "Microphone permission granted")
        return grant

    def start_foreground_service(self) -> bool:
        """Starts AssistantForegroundService with microphone type for screen-off capture."""
        if not self.has_mic_permission or not self.has_notification_permission:
            return False
        self.is_foreground_service_running = True
        return True

    def stop_foreground_service(self) -> None:
        self.is_foreground_service_running = False

    # -----------------------------------------------------------------------
    # 3. Gateway Connection & Audio Streaming
    # -----------------------------------------------------------------------

    async def connect_to_gateway(self) -> MobileRegistrationResponse:
        """Initializes device and completes gateway registration handshake."""
        self.transition_to(MobileAssistantState.INITIALIZING, "Starting registration")

        metadata = MobileDeviceMetadata(
            device_id=self.device_id,
            model=self.model,
            api_level=self.api_level,
            battery_level=self.battery_pct,
            is_charging=False,
            is_screen_on=self.is_screen_on,
            is_default_assistant=self.is_default_assistant,
            has_mic_permission=self.has_mic_permission,
            has_notification_permission=self.has_notification_permission,
        )

        req = MobileRegistrationRequest(
            device_id=self.device_id,
            auth_token=self.auth_token,
            device_metadata=metadata,
            preferred_language="en",
        )

        res = await self.adapter.register_device(req)
        if res.success:
            self.active_session_id = res.session_id
            self.transition_to(MobileAssistantState.READY, "Registration successful")
        else:
            self.transition_to(
                MobileAssistantState.ERROR, res.error_message or "Registration failed"
            )
        return res

    async def trigger_wake_phrase(self, phrase: str = "hey pixel") -> bool:
        """Simulates HotwordDetector detecting activation phrase."""
        if self.state not in (MobileAssistantState.READY, MobileAssistantState.LISTENING):
            return False

        if phrase.lower().strip() not in self.enrolled_hotwords:
            return False

        self.transition_to(MobileAssistantState.WAKE_DETECTED, f"Phrase '{phrase}' detected")
        self.transition_to(MobileAssistantState.PROCESSING, "Opening VoiceInteractionSession")
        return True

    async def stream_audio_chunk(self, pcm_bytes: bytes) -> dict[str, Any]:
        """Streams audio chunk to PIXEL Gateway."""
        if not self.active_session_id:
            return {"error": "Not connected to gateway"}

        b64_data = base64.b64encode(pcm_bytes).decode("ascii")
        packet = MobileVoicePacket(
            session_id=self.active_session_id,
            event_type="audio_frame",
            pcm_base64=b64_data,
            sample_rate=16000,
        )
        self.captured_packets.append(packet)
        return await self.adapter.handle_voice_packet(packet)

    async def send_barge_in_interruption(self) -> dict[str, Any]:
        """Sends instant barge-in signal to stop assistant speech."""
        if not self.active_session_id:
            return {"error": "Not connected to gateway"}

        if self.state == MobileAssistantState.SPEAKING:
            self.transition_to(MobileAssistantState.INTERRUPTED, "User barge-in detected")

        packet = MobileVoicePacket(
            session_id=self.active_session_id,
            event_type="barge_in",
        )
        res = await self.adapter.handle_voice_packet(packet)
        self.transition_to(
            MobileAssistantState.LISTENING, "Transitioning to listening after interrupt"
        )
        return res

    def authorize_approval_card(
        self,
        approval_request: MobileApprovalRequest,
        confirm: bool = True,
        use_biometrics: bool = True,
    ) -> MobileApprovalResponse:
        """Simulates Android user biometric / PIN confirmation on ApprovalCard."""
        return MobileApprovalResponse(
            approval_id=approval_request.approval_id,
            task_id=approval_request.task_id,
            confirmation_token=approval_request.confirmation_token,
            user_approved=confirm,
            biometric_authenticated=use_biometrics if confirm else False,
        )
