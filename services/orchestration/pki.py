"""PKI & Cryptographic mTLS Device Identity Engine.

Provides Root CA certificate generation, device CSR signing, X.509/PIXEL
certificate validation, fingerprint calculation, challenge-response verification,
and certificate revocation list (CRL) management.
"""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    DeviceTrustState,
    PairingChallenge,
    PairingConfirmation,
    PairingRequest,
    PairingResponse,
)


class PKIEngine:
    """Canonical Public Key Infrastructure and mTLS Identity Authority for PIXEL."""

    def __init__(self, root_ca_name: str = "PIXEL-Trust-Root-CA") -> None:
        self.root_ca_name = root_ca_name
        self._root_key: bytes = secrets.token_bytes(32)
        self.root_ca_cert_pem = self._generate_root_ca_cert()
        self._revocation_ledger: dict[str, dict[str, Any]] = {}
        self._active_challenges: dict[str, PairingChallenge] = {}

    def _generate_root_ca_cert(self) -> str:
        payload = {
            "serial": uuid4().hex,
            "subject": f"CN={self.root_ca_name}",
            "issuer": f"CN={self.root_ca_name}",
            "is_ca": True,
            "not_before": datetime.now(UTC).isoformat(),
            "not_after": (datetime.now(UTC) + timedelta(days=3650)).isoformat(),
            "key_id": hashlib.sha256(self._root_key).hexdigest()[:16],
        }
        sig = hmac.new(self._root_key, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        cert_data = {"payload": payload, "signature": sig}
        encoded = base64.b64encode(json.dumps(cert_data).encode()).decode()
        return f"-----BEGIN PIXEL ROOT CA CERTIFICATE-----\n{encoded}\n-----END PIXEL ROOT CA CERTIFICATE-----"

    def compute_fingerprint(self, raw_key_or_cert: str) -> str:
        """Compute SHA-256 fingerprint for a public key or certificate."""
        clean_key = raw_key_or_cert.strip()
        digest = hashlib.sha256(clean_key.encode("utf-8")).hexdigest()
        return ":".join(digest[i : i + 2] for i in range(0, 64, 2))

    def issue_device_certificate(
        self,
        device_id: str,
        role: DeviceRole,
        capabilities: list[DeviceCapability],
        public_key_pem: str,
        validity_days: int = 365,
    ) -> str:
        """Issue and cryptographically sign a device mTLS certificate."""
        now = datetime.now(UTC)
        serial = uuid4().hex
        payload = {
            "serial": serial,
            "subject": f"CN={device_id}",
            "device_id": device_id,
            "role": role.value,
            "capabilities": [c.value for c in capabilities],
            "public_key_fingerprint": self.compute_fingerprint(public_key_pem),
            "issuer": f"CN={self.root_ca_name}",
            "not_before": now.isoformat(),
            "not_after": (now + timedelta(days=validity_days)).isoformat(),
        }
        sig = hmac.new(self._root_key, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        cert_envelope = {"payload": payload, "signature": sig}
        encoded = base64.b64encode(json.dumps(cert_envelope).encode()).decode()
        return f"-----BEGIN PIXEL CERTIFICATE-----\n{encoded}\n-----END PIXEL CERTIFICATE-----"

    def validate_certificate(self, cert_pem: str) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Validate a certificate against the Root CA, expiry window, and revocation ledger.

        Returns: (is_valid, error_reason, cert_payload)
        """
        try:
            lines = cert_pem.strip().splitlines()
            if len(lines) < 3 or not lines[0].startswith("-----BEGIN PIXEL CERTIFICATE"):
                return False, "Invalid certificate PEM format", None

            b64_content = "".join(line for line in lines if not line.startswith("-----"))
            raw_bytes = base64.b64decode(b64_content)
            cert_envelope = json.loads(raw_bytes.decode())

            payload = cert_envelope.get("payload")
            signature = cert_envelope.get("signature")

            if not payload or not signature:
                return False, "Malformed certificate structure", None

            # Verify cryptographic signature against Root CA key
            expected_sig = hmac.new(
                self._root_key, json.dumps(payload, sort_keys=True).encode(), hashlib.sha256
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return False, "Signature verification failed: invalid Root CA signature", None

            # Verify temporal validity
            now = datetime.now(UTC)
            not_before = datetime.fromisoformat(payload["not_before"])
            not_after = datetime.fromisoformat(payload["not_after"])

            if now < not_before:
                return False, "Certificate is not yet valid", None
            if now > not_after:
                return False, "Certificate has expired", None

            # Verify revocation status
            device_id = payload.get("device_id", "")
            serial = payload.get("serial", "")
            if self.is_revoked(serial=serial, device_id=device_id):
                return False, f"Certificate has been revoked for device {device_id}", None

            return True, None, payload

        except Exception as exc:
            return False, f"Certificate validation exception: {exc}", None

    def create_pairing_challenge(self, device_id: str, ttl_seconds: int = 120) -> PairingChallenge:
        """Create an ephemeral pairing challenge with anti-brute-force rate limiting."""
        pin = f"{secrets.randbelow(900000) + 100000:06d}"  # Cryptographically secure 6-digit PIN
        salt = secrets.token_hex(16)
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

        challenge = PairingChallenge(
            challenge_id=uuid4().hex,
            device_id=device_id,
            pin_code=pin,
            nonce=salt,
            expires_at=expires_at,
            attempts_remaining=3,
        )
        self._active_challenges[challenge.challenge_id] = challenge
        return challenge

    def verify_pairing_confirmation(
        self,
        confirmation: PairingConfirmation,
        request: PairingRequest,
    ) -> PairingResponse:
        """Verify user authorization response for pairing challenge and provision certificate."""
        challenge = self._active_challenges.get(confirmation.challenge_id)
        if not challenge:
            return PairingResponse(
                success=False,
                device_id=confirmation.device_id,
                trust_state=DeviceTrustState.UNPAIRED,
                error_message="Pairing challenge not found or already consumed",
            )

        # Check expiry
        if datetime.now(UTC) > challenge.expires_at:
            self._active_challenges.pop(confirmation.challenge_id, None)
            return PairingResponse(
                success=False,
                device_id=confirmation.device_id,
                trust_state=DeviceTrustState.UNPAIRED,
                error_message="Pairing challenge expired",
            )

        # Check rate limit / attempts remaining
        if challenge.attempts_remaining <= 0:
            self._active_challenges.pop(confirmation.challenge_id, None)
            return PairingResponse(
                success=False,
                device_id=confirmation.device_id,
                trust_state=DeviceTrustState.BLOCKED,
                error_message="Max pairing attempts exceeded; challenge blocked",
            )

        # Verify device ID binding
        if challenge.device_id != confirmation.device_id or challenge.device_id != request.device_id:
            return PairingResponse(
                success=False,
                device_id=confirmation.device_id,
                trust_state=DeviceTrustState.UNPAIRED,
                error_message="Device ID mismatch in pairing challenge",
            )

        # Verify PIN constant-time
        pin_valid = hmac.compare_digest(challenge.pin_code, confirmation.pin_code)
        if not pin_valid or not confirmation.user_confirmed:
            challenge.attempts_remaining -= 1
            if challenge.attempts_remaining <= 0:
                self._active_challenges.pop(confirmation.challenge_id, None)
            return PairingResponse(
                success=False,
                device_id=confirmation.device_id,
                trust_state=DeviceTrustState.UNPAIRED,
                error_message="Invalid pairing PIN code or user rejected authorization",
            )

        # Success: consume challenge immediately to prevent replay
        self._active_challenges.pop(confirmation.challenge_id, None)

        cert_pem = self.issue_device_certificate(
            device_id=request.device_id,
            role=request.device_role,
            capabilities=request.capabilities,
            public_key_pem=request.public_key_pem,
        )

        return PairingResponse(
            success=True,
            device_id=request.device_id,
            certificate_pem=cert_pem,
            root_ca_pem=self.root_ca_cert_pem,
            trust_state=DeviceTrustState.TRUSTED,
            error_message=None,
        )

    def revoke_certificate(self, serial: str, device_id: str, reason: str = "Admin revocation") -> bool:
        """Revoke a certificate by serial number or device ID."""
        self._revocation_ledger[serial] = {
            "device_id": device_id,
            "serial": serial,
            "reason": reason,
            "revoked_at": datetime.now(UTC).isoformat(),
        }
        self._revocation_ledger[device_id] = {
            "device_id": device_id,
            "serial": serial,
            "reason": reason,
            "revoked_at": datetime.now(UTC).isoformat(),
        }
        return True

    def is_revoked(self, serial: str, device_id: str) -> bool:
        """Check whether a certificate serial or device is in the revocation ledger."""
        return serial in self._revocation_ledger or device_id in self._revocation_ledger
