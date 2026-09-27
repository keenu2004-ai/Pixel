"""Canonical Device Identity and Presence Registries.

Maintains trusted device hardware identities, cryptographic profiles,
capabilities, heartbeats, and real-time network presence states.
"""

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceHealthState,
    DeviceIdentity,
    DevicePresenceRecord,
    DevicePresenceState,
    DeviceRole,
    DeviceTrustState,
    PairingChallenge,
    PairingConfirmation,
    PairingRequest,
    PairingResponse,
)
from services.orchestration.pki import PKIEngine


class DeviceRegistry:
    """Canonical registry of known and trusted PIXEL nodes and satellites."""

    def __init__(self, pki_engine: PKIEngine | None = None) -> None:
        self.pki = pki_engine or PKIEngine()
        self._devices: dict[str, DeviceIdentity] = {}
        self._pending_requests: dict[str, PairingRequest] = {}
        self._lock = threading.RLock()

    def initiate_pairing(self, request: PairingRequest) -> PairingChallenge:
        """Process an incoming pairing request and issue a timed challenge."""
        with self._lock:
            # If already revoked, block pairing
            existing = self._devices.get(request.device_id)
            if existing and existing.trust_state == DeviceTrustState.REVOKED:
                raise ValueError(f"Device {request.device_id} is REVOKED and cannot pair without administrative reset.")

            self._pending_requests[request.device_id] = request
            return self.pki.create_pairing_challenge(device_id=request.device_id)

    def complete_pairing(self, confirmation: PairingConfirmation) -> PairingResponse:
        """Validate pairing challenge authorization and register trusted device."""
        with self._lock:
            request = self._pending_requests.get(confirmation.device_id)
            if not request:
                return PairingResponse(
                    success=False,
                    device_id=confirmation.device_id,
                    trust_state=DeviceTrustState.UNPAIRED,
                    error_message="No pending pairing request found for device",
                )

            response = self.pki.verify_pairing_confirmation(confirmation, request)
            if not response.success or not response.certificate_pem:
                return response

            now = datetime.now(UTC)
            fingerprint = self.pki.compute_fingerprint(request.public_key_pem)

            identity = DeviceIdentity(
                device_id=request.device_id,
                device_type=request.device_role,
                device_name=request.device_name,
                public_key_fingerprint=fingerprint,
                certificate_pem=response.certificate_pem,
                capabilities=request.capabilities,
                trust_state=DeviceTrustState.TRUSTED,
                created_at=now,
                updated_at=now,
            )

            self._devices[request.device_id] = identity
            self._pending_requests.pop(request.device_id, None)
            return response

    def authenticate_device_connection(self, device_id: str, cert_pem: str) -> tuple[bool, str | None]:
        """Authenticate mTLS client certificate during network connection establishment."""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return False, f"Device {device_id} not registered"

            if device.trust_state != DeviceTrustState.TRUSTED:
                return False, f"Device {device_id} is in {device.trust_state.value} state"

            is_valid, reason, payload = self.pki.validate_certificate(cert_pem)
            if not is_valid or not payload:
                return False, f"mTLS certificate validation failed: {reason}"

            if payload.get("device_id") != device_id:
                return False, "Certificate subject CN does not match connecting device ID"

            return True, None

    def get_device(self, device_id: str) -> DeviceIdentity | None:
        """Retrieve device identity by device ID."""
        with self._lock:
            return self._devices.get(device_id)

    def list_devices(
        self,
        trust_state: DeviceTrustState | None = None,
        role: DeviceRole | None = None,
    ) -> list[DeviceIdentity]:
        """List registered devices with optional filtering."""
        with self._lock:
            devices = list(self._devices.values())
            if trust_state:
                devices = [d for d in devices if d.trust_state == trust_state]
            if role:
                devices = [d for d in devices if d.device_type == role]
            return devices

    def find_devices_with_capability(self, capability: DeviceCapability) -> list[DeviceIdentity]:
        """Find all trusted devices supporting a specific hardware capability."""
        with self._lock:
            return [
                d
                for d in self._devices.values()
                if d.trust_state == DeviceTrustState.TRUSTED and capability in d.capabilities
            ]

    def revoke_device(self, device_id: str, reason: str = "Admin action") -> bool:
        """Revoke device trust and invalidate its mTLS certificate."""
        with self._lock:
            device = self._devices.get(device_id)
            if not device:
                return False

            device.trust_state = DeviceTrustState.REVOKED
            device.updated_at = datetime.now(UTC)

            if device.certificate_pem:
                self.pki.revoke_certificate(serial="", device_id=device_id, reason=reason)

            return True

    def remove_device(self, device_id: str) -> bool:
        """Remove device from registry completely."""
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                self._pending_requests.pop(device_id, None)
                return True
            return False


class PresenceManager:
    """Manages real-time presence heartbeats and stale-device auto-detection."""

    def __init__(self, heartbeat_timeout_seconds: float = 30.0) -> None:
        self.heartbeat_timeout_seconds = heartbeat_timeout_seconds
        self._presence: dict[str, DevicePresenceRecord] = {}
        self._lock = threading.RLock()

    def update_heartbeat(
        self,
        device_id: str,
        rtt_ms: float = 0.0,
        battery_level: int | None = None,
        is_charging: bool = False,
        active_session_id: str | None = None,
        health_state: DeviceHealthState = DeviceHealthState.HEALTHY,
        metadata: dict[str, Any] | None = None,
    ) -> DevicePresenceRecord:
        """Record an incoming heartbeat from an active device."""
        with self._lock:
            now = datetime.now(UTC)
            record = self._presence.get(device_id)
            if not record:
                record = DevicePresenceRecord(
                    device_id=device_id,
                    presence_state=DevicePresenceState.ONLINE,
                    health_state=health_state,
                    last_heartbeat=now,
                    rtt_ms=rtt_ms,
                    battery_level=battery_level,
                    is_charging=is_charging,
                    active_session_id=active_session_id,
                    metadata=metadata or {},
                )
                self._presence[device_id] = record
            else:
                record.presence_state = DevicePresenceState.ONLINE
                record.health_state = health_state
                record.last_heartbeat = now
                record.rtt_ms = rtt_ms
                if battery_level is not None:
                    record.battery_level = battery_level
                record.is_charging = is_charging
                record.active_session_id = active_session_id
                if metadata:
                    record.metadata.update(metadata)

            return record

    def get_presence(self, device_id: str) -> DevicePresenceRecord | None:
        """Get current presence record for a device."""
        with self._lock:
            return self._presence.get(device_id)

    def set_device_offline(self, device_id: str) -> None:
        """Explicitly set a device to OFFLINE state."""
        with self._lock:
            record = self._presence.get(device_id)
            if record:
                record.presence_state = DevicePresenceState.OFFLINE
                record.health_state = DeviceHealthState.UNAVAILABLE

    def sweep_stale_devices(self, now: datetime | None = None) -> list[str]:
        """Mark devices with expired heartbeats as OFFLINE. Returns list of newly stale device IDs."""
        current_time = now or datetime.now(UTC)
        cutoff = current_time - timedelta(seconds=self.heartbeat_timeout_seconds)
        stale_ids = []

        with self._lock:
            for device_id, record in self._presence.items():
                if record.presence_state == DevicePresenceState.ONLINE and record.last_heartbeat < cutoff:
                    record.presence_state = DevicePresenceState.OFFLINE
                    record.health_state = DeviceHealthState.UNAVAILABLE
                    stale_ids.append(device_id)

        return stale_ids

    def get_online_devices(self) -> list[DevicePresenceRecord]:
        """Return list of all currently ONLINE devices."""
        with self._lock:
            self.sweep_stale_devices()
            return [r for r in self._presence.values() if r.presence_state == DevicePresenceState.ONLINE]
