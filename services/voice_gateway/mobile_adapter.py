"""Mobile Gateway Adapter & Android Device Bridge.

Coordinates Android client registration, token authentication,
device telemetry tracking, streaming voice forwarding, and mobile approval card exchange.
"""

import hmac
import logging
from typing import Any
from uuid import uuid4

from packages.contracts.events import VoiceState
from packages.contracts.mobile import (
    MobileApprovalRequest,
    MobileApprovalResponse,
    MobileDeviceMetadata,
    MobileRegistrationRequest,
    MobileRegistrationResponse,
    MobileVoicePacket,
)
from services.voice_gateway.pipeline import VoicePipeline
from services.voice_gateway.session import VoiceSession

logger = logging.getLogger(__name__)


class MobileGatewayAdapter:
    """Server-side coordinator for Android clients connecting to PIXEL Voice Gateway."""

    def __init__(
        self,
        pipeline: VoicePipeline | None = None,
        shared_auth_secret: str = "pixel_mobile_device_auth_secret_v1",
    ) -> None:
        self.pipeline = pipeline
        self.shared_auth_secret = shared_auth_secret
        self.registered_devices: dict[str, MobileDeviceMetadata] = {}
        self.sessions: dict[str, VoiceSession] = {}
        self.device_sessions: dict[str, str] = {}  # device_id -> session_id
        self.pending_mobile_approvals: dict[str, MobileApprovalRequest] = {}

    def authenticate_token(self, token: str) -> bool:
        """Validates mobile client authorization token."""
        if not token:
            return False
        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(token.strip(), self.shared_auth_secret)

    async def get_or_create_session(self, session_id: str) -> VoiceSession:
        """Retrieves or creates a VoiceSession."""
        if session_id not in self.sessions:
            self.sessions[session_id] = VoiceSession(session_id=session_id)
        return self.sessions[session_id]

    async def get_session(self, session_id: str) -> VoiceSession | None:
        """Retrieves a VoiceSession if active."""
        return self.sessions.get(session_id)

    async def register_device(self, request: MobileRegistrationRequest) -> MobileRegistrationResponse:
        """Handles client handshake, validates auth, and binds session."""
        if not self.authenticate_token(request.auth_token):
            logger.warning("Mobile registration rejected: Invalid token for device %s", request.device_id)
            return MobileRegistrationResponse(
                success=False,
                error_message="Authentication failed: Invalid authorization token.",
            )

        # Store or update device metadata
        self.registered_devices[request.device_id] = request.device_metadata

        # Create or allocate voice gateway session
        session_id = f"mobile_{request.device_id[:8]}_{uuid4().hex[:6]}"
        session = await self.get_or_create_session(session_id)
        self.device_sessions[request.device_id] = session.session_id
        logger.info("Registered Android device %s bound to session %s", request.device_id, session.session_id)

        return MobileRegistrationResponse(
            success=True,
            session_id=session.session_id,
            websocket_url=f"/ws/voice?session_id={session.session_id}",
            heartbeat_interval_seconds=30,
        )

    async def handle_voice_packet(self, packet: MobileVoicePacket) -> dict[str, Any]:
        """Processes audio chunks, wake detections, and interruption signals from Android."""
        session = await self.get_session(packet.session_id)
        if not session:
            return {"status": "error", "message": f"Session {packet.session_id} not found."}

        if packet.event_type == "barge_in":
            # Interrupt active synthesis immediately
            session.cancel_active_playback()
            session.transition_to(VoiceState.INTERRUPTED, "Mobile client sent barge-in")
            return {"status": "interrupted", "session_id": packet.session_id}

        if packet.event_type == "audio_frame" and packet.pcm_base64:
            import base64

            from packages.contracts.events import AudioFrame
            pcm_bytes = base64.b64decode(packet.pcm_base64)
            # Write to session audio buffer
            frame = AudioFrame(
                sample_rate=packet.sample_rate,
                pcm_data=pcm_bytes,
                timestamp_ms=packet.timestamp_ms,
            )
            await session.buffer.push(frame)
            return {"status": "processed", "bytes_received": len(pcm_bytes)}

        return {"status": "acknowledged", "event_type": packet.event_type}

    def dispatch_approval_request(
        self,
        task_id: str,
        tool_name: str,
        risk_class: str,
        reason: str,
        confirmation_token: str,
        arguments: dict[str, Any],
    ) -> MobileApprovalRequest:
        """Dispatches an L6 approval card to the mobile UI."""
        approval_id = uuid4().hex
        card = MobileApprovalRequest(
            approval_id=approval_id,
            task_id=task_id,
            tool_name=tool_name,
            risk_class=risk_class,
            reason=reason,
            arguments_summary=arguments,
            confirmation_token=confirmation_token,
        )
        self.pending_mobile_approvals[approval_id] = card
        return card

    def process_approval_response(self, response: MobileApprovalResponse) -> tuple[bool, str | None]:
        """Validates and consumes user biometric / touch approval from Android."""
        card = self.pending_mobile_approvals.get(response.approval_id)
        if not card:
            return False, "Approval card not found or expired."

        if not hmac.compare_digest(card.confirmation_token, response.confirmation_token):
            return False, "Security violation: Confirmation token mismatch / replay detected."

        # Successfully consumed
        self.pending_mobile_approvals.pop(response.approval_id, None)
        return True, None
