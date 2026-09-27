"""Unit tests for PKIEngine and mTLS cryptographic certificate lifecycle."""

import base64
import json

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    DeviceTrustState,
    PairingConfirmation,
    PairingRequest,
)
from services.orchestration.pki import PKIEngine


def test_pki_root_ca_and_fingerprint() -> None:
    pki = PKIEngine()
    assert "BEGIN PIXEL ROOT CA CERTIFICATE" in pki.root_ca_cert_pem
    fingerprint = pki.compute_fingerprint("my-test-key-or-cert")
    assert len(fingerprint.split(":")) == 32


def test_device_certificate_issuance_and_validation() -> None:
    pki = PKIEngine()
    cert_pem = pki.issue_device_certificate(
        device_id="node-desktop-1",
        role=DeviceRole.PRIMARY_PC,
        capabilities=[DeviceCapability.DESKTOP_CONTROL, DeviceCapability.MICROPHONE],
        public_key_pem="fake-pem-key",
    )
    assert "BEGIN PIXEL CERTIFICATE" in cert_pem

    is_valid, error, payload = pki.validate_certificate(cert_pem)
    assert is_valid is True
    assert error is None
    assert payload is not None
    assert payload["device_id"] == "node-desktop-1"
    assert payload["role"] == DeviceRole.PRIMARY_PC.value
    assert DeviceCapability.DESKTOP_CONTROL.value in payload["capabilities"]


def test_tampered_certificate_rejected() -> None:
    pki = PKIEngine()
    cert_pem = pki.issue_device_certificate(
        device_id="node-desktop-1",
        role=DeviceRole.PRIMARY_PC,
        capabilities=[DeviceCapability.DESKTOP_CONTROL],
        public_key_pem="fake-pem-key",
    )
    lines = cert_pem.strip().splitlines()
    b64_content = "".join(line for line in lines if not line.startswith("-----"))
    cert_envelope = json.loads(base64.b64decode(b64_content).decode())

    # Tamper with device_id in payload without updating signature
    cert_envelope["payload"]["device_id"] = "attacker-node"
    tampered_b64 = base64.b64encode(json.dumps(cert_envelope).encode()).decode()
    tampered_pem = (
        f"-----BEGIN PIXEL CERTIFICATE-----\n{tampered_b64}\n-----END PIXEL CERTIFICATE-----"
    )

    is_valid, error, payload = pki.validate_certificate(tampered_pem)
    assert is_valid is False
    assert "Signature verification failed" in (error or "")


def test_expired_certificate_rejected() -> None:
    pki = PKIEngine()
    # Issue certificate with negative validity days (already expired)
    cert_pem = pki.issue_device_certificate(
        device_id="node-desktop-1",
        role=DeviceRole.PRIMARY_PC,
        capabilities=[DeviceCapability.DESKTOP_CONTROL],
        public_key_pem="fake-pem-key",
        validity_days=-1,
    )
    is_valid, error, payload = pki.validate_certificate(cert_pem)
    assert is_valid is False
    assert "Certificate has expired" in (error or "")


def test_revoked_certificate_rejected() -> None:
    pki = PKIEngine()
    cert_pem = pki.issue_device_certificate(
        device_id="node-compromised",
        role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.MICROPHONE],
        public_key_pem="fake-pem-key",
    )
    is_valid, _, _ = pki.validate_certificate(cert_pem)
    assert is_valid is True

    pki.revoke_certificate(serial="", device_id="node-compromised", reason="Device lost")
    is_valid_after, error_after, _ = pki.validate_certificate(cert_pem)
    assert is_valid_after is False
    assert "revoked" in (error_after or "")


def test_pairing_challenge_and_pin_verification() -> None:
    pki = PKIEngine()
    req = PairingRequest(
        device_id="satellite-kitchen",
        device_name="Kitchen Satellite",
        device_role=DeviceRole.SATELLITE_MIC_SPEAKER,
        capabilities=[DeviceCapability.MICROPHONE, DeviceCapability.SPEAKER],
        public_key_pem="pub-key-pem",
    )

    challenge = pki.create_pairing_challenge(device_id="satellite-kitchen")
    assert challenge.device_id == "satellite-kitchen"
    assert len(challenge.pin_code) == 6

    # Test wrong PIN
    bad_conf = PairingConfirmation(
        challenge_id=challenge.challenge_id,
        device_id="satellite-kitchen",
        pin_code="000000",
        user_confirmed=True,
    )
    bad_resp = pki.verify_pairing_confirmation(bad_conf, req)
    assert bad_resp.success is False
    assert bad_resp.trust_state == DeviceTrustState.UNPAIRED

    # Test correct PIN
    good_conf = PairingConfirmation(
        challenge_id=challenge.challenge_id,
        device_id="satellite-kitchen",
        pin_code=challenge.pin_code,
        user_confirmed=True,
    )
    good_resp = pki.verify_pairing_confirmation(good_conf, req)
    assert good_resp.success is True
    assert good_resp.trust_state == DeviceTrustState.TRUSTED
    assert good_resp.certificate_pem is not None

    # Replay of consumed challenge should fail
    replay_resp = pki.verify_pairing_confirmation(good_conf, req)
    assert replay_resp.success is False
    assert "not found" in (replay_resp.error_message or "")
