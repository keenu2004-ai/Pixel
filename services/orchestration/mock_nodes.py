"""Deterministic Mock Distributed Topology Nodes.

Simulates PC nodes, Android mobile devices, and room satellite microphones
for automated, hardware-free CI integration testing.
"""

import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    PairingChallenge,
    PairingConfirmation,
    PairingRequest,
    PairingResponse,
    WakeArbitrationCandidate,
    WakeArbitrationResult,
)
from services.orchestration.arbitration import WakeArbiter
from services.orchestration.registry import PresenceManager


class MockDeviceNode:
    """Base class for deterministic distributed test nodes."""

    def __init__(
        self,
        device_id: str,
        device_name: str,
        role: DeviceRole,
        capabilities: list[DeviceCapability],
    ) -> None:
        self.device_id = device_id
        self.device_name = device_name
        self.role = role
        self.capabilities = capabilities
        self.private_key = secrets.token_bytes(32)
        self.public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{secrets.token_hex(32)}\n-----END PUBLIC KEY-----"
        self.certificate_pem: str | None = None
        self.root_ca_pem: str | None = None
        self.is_connected = False
        self.active_session_id: str | None = None

    def create_pairing_request(self) -> PairingRequest:
        """Construct a pairing request from node identity."""
        return PairingRequest(
            device_id=self.device_id,
            device_name=self.device_name,
            device_role=self.role,
            capabilities=self.capabilities,
            public_key_pem=self.public_key_pem,
            nonce=uuid4().hex,
            timestamp=datetime.now(UTC),
        )

    def answer_pairing_challenge(
        self,
        challenge: PairingChallenge,
        override_pin: str | None = None,
        confirm: bool = True,
    ) -> PairingConfirmation:
        """Create authorization response to pairing challenge."""
        return PairingConfirmation(
            challenge_id=challenge.challenge_id,
            device_id=self.device_id,
            pin_code=override_pin if override_pin is not None else challenge.pin_code,
            user_confirmed=confirm,
            auth_signature=secrets.token_hex(16),
        )

    def install_certificate(self, response: PairingResponse) -> None:
        """Install provisioned mTLS certificate received from Core."""
        if response.success and response.certificate_pem:
            self.certificate_pem = response.certificate_pem
            self.root_ca_pem = response.root_ca_pem
            self.is_connected = True

    def send_heartbeat(
        self,
        presence_mgr: PresenceManager,
        rtt_ms: float = 5.0,
        battery_level: int | None = None,
        is_charging: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Emit heartbeat telemetry to central PresenceManager."""
        presence_mgr.update_heartbeat(
            device_id=self.device_id,
            rtt_ms=rtt_ms,
            battery_level=battery_level,
            is_charging=is_charging,
            active_session_id=self.active_session_id,
            metadata=metadata,
        )

    def emit_wake_candidate(
        self,
        arbiter: WakeArbiter,
        wake_event_id: str,
        timestamp_ms: int,
        confidence: float = 0.95,
        snr_db: float = 18.0,
        estimated_distance_m: float = 1.0,
        rtt_ms: float = 5.0,
        is_current_owner: bool = False,
    ) -> WakeArbitrationResult:
        """Emit local wake-word detection candidate frame to WakeArbiter."""
        candidate = WakeArbitrationCandidate(
            candidate_id=uuid4().hex,
            device_id=self.device_id,
            wake_event_id=wake_event_id,
            timestamp_ms=timestamp_ms,
            confidence=confidence,
            snr_db=snr_db,
            estimated_distance_m=estimated_distance_m,
            is_current_interaction_owner=is_current_owner,
            rtt_ms=rtt_ms,
        )
        return arbiter.register_candidate(candidate)


class MockPCNode(MockDeviceNode):
    """Simulated desktop/workstation node with coding and desktop control capabilities."""

    def __init__(self, device_id: str = "pc-workstation-01", device_name: str = "Primary Desktop") -> None:
        super().__init__(
            device_id=device_id,
            device_name=device_name,
            role=DeviceRole.PRIMARY_PC,
            capabilities=[
                DeviceCapability.DESKTOP_CONTROL,
                DeviceCapability.CODE_EXECUTION,
                DeviceCapability.MICROPHONE,
                DeviceCapability.SPEAKER,
                DeviceCapability.DISPLAY,
                DeviceCapability.WAKE_WORD,
                DeviceCapability.LOCAL_LLM,
            ],
        )


class MockAndroidNode(MockDeviceNode):
    """Simulated Android mobile assistant node with battery and mobile control."""

    def __init__(self, device_id: str = "android-pixel-01", device_name: str = "Pixel 8 Pro") -> None:
        super().__init__(
            device_id=device_id,
            device_name=device_name,
            role=DeviceRole.MOBILE_NODE,
            capabilities=[
                DeviceCapability.ANDROID_CONTROL,
                DeviceCapability.MICROPHONE,
                DeviceCapability.SPEAKER,
                DeviceCapability.DISPLAY,
                DeviceCapability.BATTERY,
                DeviceCapability.WAKE_WORD,
                DeviceCapability.CAMERA,
            ],
        )


class MockSatelliteNode(MockDeviceNode):
    """Simulated lightweight room satellite microphone/speaker node."""

    def __init__(self, device_id: str = "satellite-livingroom-01", device_name: str = "Living Room Satellite") -> None:
        super().__init__(
            device_id=device_id,
            device_name=device_name,
            role=DeviceRole.SATELLITE_MIC_SPEAKER,
            capabilities=[
                DeviceCapability.MICROPHONE,
                DeviceCapability.SPEAKER,
                DeviceCapability.WAKE_WORD,
            ],
        )
