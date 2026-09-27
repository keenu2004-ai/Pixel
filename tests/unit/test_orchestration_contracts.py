"""Unit tests for multi-device orchestration contracts and enums."""

from datetime import UTC, datetime

from packages.contracts.orchestration import (
    ContextHandoffPayload,
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
    TaskHandoffPayload,
    WakeArbitrationCandidate,
    WakeArbitrationResult,
)


def test_orchestration_enums() -> None:
    assert DeviceRole.PRIMARY_PC == "PRIMARY_PC"
    assert DeviceRole.MOBILE_NODE == "MOBILE_NODE"
    assert DeviceRole.SATELLITE_MIC_SPEAKER == "SATELLITE_MIC_SPEAKER"

    assert DeviceCapability.MICROPHONE == "MICROPHONE"
    assert DeviceCapability.DESKTOP_CONTROL == "DESKTOP_CONTROL"
    assert DeviceCapability.ANDROID_CONTROL == "ANDROID_CONTROL"

    assert DeviceTrustState.UNPAIRED == "UNPAIRED"
    assert DeviceTrustState.TRUSTED == "TRUSTED"
    assert DeviceTrustState.REVOKED == "REVOKED"

    assert DevicePresenceState.ONLINE == "ONLINE"
    assert DevicePresenceState.OFFLINE == "OFFLINE"
    assert DeviceHealthState.HEALTHY == "HEALTHY"


def test_device_identity_contract() -> None:
    now = datetime.now(UTC)
    identity = DeviceIdentity(
        device_id="dev-123",
        device_type=DeviceRole.PRIMARY_PC,
        device_name="My PC",
        public_key_fingerprint="aa:bb:cc:dd",
        capabilities=[DeviceCapability.DESKTOP_CONTROL, DeviceCapability.MICROPHONE],
        trust_state=DeviceTrustState.TRUSTED,
        created_at=now,
        updated_at=now,
    )
    assert identity.device_id == "dev-123"
    assert identity.capabilities == [DeviceCapability.DESKTOP_CONTROL, DeviceCapability.MICROPHONE]
    assert identity.trust_state == DeviceTrustState.TRUSTED


def test_device_presence_record_contract() -> None:
    record = DevicePresenceRecord(
        device_id="sat-01",
        presence_state=DevicePresenceState.ONLINE,
        health_state=DeviceHealthState.HEALTHY,
        rtt_ms=12.5,
        battery_level=85,
    )
    assert record.device_id == "sat-01"
    assert record.presence_state == DevicePresenceState.ONLINE
    assert record.rtt_ms == 12.5
    assert record.battery_level == 85


def test_pairing_contracts() -> None:
    req = PairingRequest(
        device_id="phone-01",
        device_name="Pixel Phone",
        device_role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.ANDROID_CONTROL],
        public_key_pem="fake_pem",
    )
    assert req.device_id == "phone-01"

    chal = PairingChallenge(
        device_id="phone-01",
        pin_code="123456",
        nonce="salt-123",
        expires_at=datetime.now(UTC),
    )
    assert chal.pin_code == "123456"

    conf = PairingConfirmation(
        challenge_id=chal.challenge_id,
        device_id="phone-01",
        pin_code="123456",
        user_confirmed=True,
    )
    assert conf.user_confirmed is True

    resp = PairingResponse(
        success=True,
        device_id="phone-01",
        certificate_pem="cert_data",
        trust_state=DeviceTrustState.TRUSTED,
    )
    assert resp.success is True


def test_wake_arbitration_contracts() -> None:
    cand = WakeArbitrationCandidate(
        device_id="sat-01",
        wake_event_id="wake-abc",
        timestamp_ms=1000,
        confidence=0.98,
        snr_db=22.0,
    )
    assert cand.device_id == "sat-01"
    assert cand.confidence == 0.98

    res = WakeArbitrationResult(
        wake_event_id="wake-abc",
        winner_device_id="sat-01",
        winner_score=145.0,
        suppressed_device_ids=["sat-02", "sat-03"],
        candidates_evaluated=3,
    )
    assert res.winner_device_id == "sat-01"
    assert len(res.suppressed_device_ids) == 2


def test_handoff_contracts() -> None:
    ctx = ContextHandoffPayload(
        source_device_id="phone-01",
        target_device_id="pc-01",
        session_id="sess-01",
        conversation_context={"key": "val"},
    )
    assert ctx.source_device_id == "phone-01"

    task = TaskHandoffPayload(
        task_id="task-101",
        source_device_id="phone-01",
        target_device_id="pc-01",
        task_version=2,
        concurrency_lease_token="lease_token_xyz",
        plan_steps=[{"step": 1}],
    )
    assert task.task_version == 2
    assert task.concurrency_lease_token == "lease_token_xyz"

