"""Hostile Security & Invariant Verification Suite for Phase 7 Orchestration."""

import base64
import json

import pytest

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    DeviceTrustState,
    PairingConfirmation,
    PairingRequest,
)
from services.orchestration.handoff import HandoffManager
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager


def test_invariant_revoked_device_cannot_authenticate_or_re_pair() -> None:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)

    req = PairingRequest(
        device_id="malicious-dev-1",
        device_name="Malicious Node",
        device_role=DeviceRole.SATELLITE_MIC_SPEAKER,
        capabilities=[DeviceCapability.MICROPHONE],
        public_key_pem="pubkey",
    )
    chal = registry.initiate_pairing(req)
    resp = registry.complete_pairing(PairingConfirmation(challenge_id=chal.challenge_id, device_id=req.device_id, pin_code=chal.pin_code, user_confirmed=True))
    assert resp.success is True
    assert resp.certificate_pem is not None

    # Revoke
    registry.revoke_device(req.device_id, reason="Compromised key")

    # Invariant: Auth fails
    auth_ok, auth_err = registry.authenticate_device_connection(req.device_id, resp.certificate_pem)
    assert auth_ok is False
    assert "REVOKED" in (auth_err or "")

    # Invariant: Re-pairing is blocked
    with pytest.raises(ValueError, match="REVOKED"):
        registry.initiate_pairing(req)


def test_invariant_pairing_pin_brute_force_blocked() -> None:
    pki = PKIEngine()
    req = PairingRequest(
        device_id="dev-victim",
        device_name="Victim Node",
        device_role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.MICROPHONE],
        public_key_pem="pubkey",
    )
    chal = pki.create_pairing_challenge(device_id="dev-victim")

    # 3 bad attempts
    for _ in range(3):
        conf = PairingConfirmation(
            challenge_id=chal.challenge_id,
            device_id="dev-victim",
            pin_code="000000",
            user_confirmed=True,
        )
        resp = pki.verify_pairing_confirmation(conf, req)
        assert resp.success is False

    # 4th attempt with correct pin is BLOCKED because max attempts exceeded
    conf_correct = PairingConfirmation(
        challenge_id=chal.challenge_id,
        device_id="dev-victim",
        pin_code=chal.pin_code,
        user_confirmed=True,
    )
    resp_blocked = pki.verify_pairing_confirmation(conf_correct, req)
    assert resp_blocked.success is False
    assert resp_blocked.trust_state in (DeviceTrustState.BLOCKED, DeviceTrustState.UNPAIRED)


def test_invariant_certificate_forgery_fails() -> None:
    pki = PKIEngine()
    # Attempting to craft a valid-looking certificate with arbitrary private key
    fake_payload = {
        "device_id": "forged-pc-01",
        "role": DeviceRole.PRIMARY_PC.value,
        "capabilities": [DeviceCapability.DESKTOP_CONTROL.value],
        "not_before": "2026-01-01T00:00:00Z",
        "not_after": "2027-01-01T00:00:00Z",
    }
    fake_envelope = {
        "payload": fake_payload,
        "signature": "deadbeef" * 8,
    }
    b64 = base64.b64encode(json.dumps(fake_envelope).encode()).decode()
    forged_cert = f"-----BEGIN PIXEL CERTIFICATE-----\n{b64}\n-----END PIXEL CERTIFICATE-----"

    is_valid, error, _ = pki.validate_certificate(forged_cert)
    assert is_valid is False
    assert "Signature verification failed" in (error or "")


def test_invariant_split_brain_task_concurrency_protection() -> None:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)
    presence = PresenceManager()

    for dev_id in ["pc-01", "phone-01"]:
        req = PairingRequest(
            device_id=dev_id,
            device_name=dev_id,
            device_role=DeviceRole.PRIMARY_PC if "pc" in dev_id else DeviceRole.MOBILE_NODE,
            capabilities=[DeviceCapability.DESKTOP_CONTROL, DeviceCapability.ANDROID_CONTROL],
            public_key_pem=f"pem-{dev_id}",
        )
        chal = registry.initiate_pairing(req)
        registry.complete_pairing(PairingConfirmation(challenge_id=chal.challenge_id, device_id=dev_id, pin_code=chal.pin_code, user_confirmed=True))
        presence.update_heartbeat(dev_id)

    handoff = HandoffManager(registry=registry, presence=presence)

    # 1. Handoff to PC version 2
    h1 = handoff.initiate_task_handoff(
        source_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task-critical",
        current_version=1,
        plan_steps=[],
    )
    assert h1.task_version == 2

    # 2. Complete handoff to PC
    assert handoff.complete_task_handoff("task-critical", "pc-01", h1.concurrency_lease_token) is True

    # 3. Old phone node tries to claim with stale version 1 -> Rejected
    with pytest.raises(RuntimeError, match="Stale task handoff"):
        handoff.initiate_task_handoff(
            source_device_id="phone-01",
            target_device_id="phone-01",
            task_id="task-critical",
            current_version=1,
            plan_steps=[],
        )

