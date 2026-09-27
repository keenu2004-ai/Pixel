"""Unit tests for DeviceRegistry and PresenceManager."""

from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.orchestration import (
    DeviceCapability,
    DevicePresenceState,
    DeviceRole,
    DeviceTrustState,
    PairingConfirmation,
    PairingRequest,
)
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager


def test_device_registry_pairing_flow() -> None:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)

    req = PairingRequest(
        device_id="android-pixel-01",
        device_name="Pixel Phone",
        device_role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.ANDROID_CONTROL, DeviceCapability.MICROPHONE],
        public_key_pem="fake-pem-key-android",
    )

    # 1. Initiate pairing -> get challenge
    challenge = registry.initiate_pairing(req)
    assert challenge.device_id == "android-pixel-01"

    # 2. Confirm pairing with PIN
    conf = PairingConfirmation(
        challenge_id=challenge.challenge_id,
        device_id="android-pixel-01",
        pin_code=challenge.pin_code,
        user_confirmed=True,
    )
    resp = registry.complete_pairing(conf)
    assert resp.success is True
    assert resp.trust_state == DeviceTrustState.TRUSTED
    assert resp.certificate_pem is not None

    # 3. Retrieve device
    dev = registry.get_device("android-pixel-01")
    assert dev is not None
    assert dev.trust_state == DeviceTrustState.TRUSTED
    assert DeviceCapability.ANDROID_CONTROL in dev.capabilities

    # 4. Authenticate mTLS connection
    auth_ok, auth_err = registry.authenticate_device_connection("android-pixel-01", resp.certificate_pem)
    assert auth_ok is True
    assert auth_err is None


def test_registry_capability_queries() -> None:
    registry = DeviceRegistry()
    for role, dev_id, caps in [
        (DeviceRole.PRIMARY_PC, "pc-01", [DeviceCapability.DESKTOP_CONTROL, DeviceCapability.CODE_EXECUTION]),
        (DeviceRole.MOBILE_NODE, "phone-01", [DeviceCapability.ANDROID_CONTROL, DeviceCapability.CAMERA]),
        (DeviceRole.SATELLITE_MIC_SPEAKER, "sat-01", [DeviceCapability.MICROPHONE, DeviceCapability.SPEAKER]),
    ]:
        req = PairingRequest(
            device_id=dev_id,
            device_name=f"Device {dev_id}",
            device_role=role,
            capabilities=caps,
            public_key_pem="pem-key",
        )
        chal = registry.initiate_pairing(req)
        conf = PairingConfirmation(
            challenge_id=chal.challenge_id,
            device_id=dev_id,
            pin_code=chal.pin_code,
            user_confirmed=True,
        )
        registry.complete_pairing(conf)

    desktop_devs = registry.find_devices_with_capability(DeviceCapability.DESKTOP_CONTROL)
    assert len(desktop_devs) == 1
    assert desktop_devs[0].device_id == "pc-01"

    android_devs = registry.find_devices_with_capability(DeviceCapability.ANDROID_CONTROL)
    assert len(android_devs) == 1
    assert android_devs[0].device_id == "phone-01"

    mic_devs = registry.find_devices_with_capability(DeviceCapability.MICROPHONE)
    assert len(mic_devs) == 1
    assert mic_devs[0].device_id == "sat-01"


def test_device_revocation_and_removal() -> None:
    registry = DeviceRegistry()
    req = PairingRequest(
        device_id="dev-bad",
        device_name="Bad Node",
        device_role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.MICROPHONE],
        public_key_pem="pem-bad",
    )
    chal = registry.initiate_pairing(req)
    conf = PairingConfirmation(
        challenge_id=chal.challenge_id,
        device_id="dev-bad",
        pin_code=chal.pin_code,
        user_confirmed=True,
    )
    resp = registry.complete_pairing(conf)
    cert = resp.certificate_pem
    assert cert is not None

    # Revoke device
    assert registry.revoke_device("dev-bad", reason="Compromised device") is True
    dev = registry.get_device("dev-bad")
    assert dev is not None
    assert dev.trust_state == DeviceTrustState.REVOKED

    # Connection authentication should now fail
    auth_ok, auth_err = registry.authenticate_device_connection("dev-bad", cert)
    assert auth_ok is False
    assert "REVOKED" in (auth_err or "")

    # Re-pairing a revoked device should raise ValueError
    with pytest.raises(ValueError, match="REVOKED"):
        registry.initiate_pairing(req)

    # Remove device completely
    assert registry.remove_device("dev-bad") is True
    assert registry.get_device("dev-bad") is None


def test_presence_manager_heartbeat_and_stale_sweep() -> None:
    presence = PresenceManager(heartbeat_timeout_seconds=5.0)

    # Heartbeat from sat-01
    presence.update_heartbeat(
        device_id="sat-01",
        rtt_ms=4.2,
        battery_level=90,
        is_charging=True,
    )
    rec = presence.get_presence("sat-01")
    assert rec is not None
    assert rec.presence_state == DevicePresenceState.ONLINE
    assert rec.rtt_ms == 4.2
    assert rec.battery_level == 90
    assert rec.is_charging is True

    # Check online devices
    online = presence.get_online_devices()
    assert len(online) == 1
    assert online[0].device_id == "sat-01"

    # Fast forward 10 seconds into the future
    future_time = datetime.now(UTC) + timedelta(seconds=10)
    stale_ids = presence.sweep_stale_devices(now=future_time)
    assert "sat-01" in stale_ids

    rec_after = presence.get_presence("sat-01")
    assert rec_after is not None
    assert rec_after.presence_state == DevicePresenceState.OFFLINE

