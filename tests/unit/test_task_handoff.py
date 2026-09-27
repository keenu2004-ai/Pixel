"""Unit tests for HandoffManager, scoped context handoff, and task migration."""

import pytest

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    PairingConfirmation,
    PairingRequest,
)
from services.orchestration.handoff import HandoffManager
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager


def _setup_environment() -> tuple[DeviceRegistry, PresenceManager, HandoffManager]:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)
    presence = PresenceManager()

    # Register PC
    pc_req = PairingRequest(
        device_id="pc-01",
        device_name="Primary Desktop",
        device_role=DeviceRole.PRIMARY_PC,
        capabilities=[DeviceCapability.DESKTOP_CONTROL, DeviceCapability.CODE_EXECUTION, DeviceCapability.MICROPHONE],
        public_key_pem="pem-pc",
    )
    chal_pc = registry.initiate_pairing(pc_req)
    registry.complete_pairing(PairingConfirmation(challenge_id=chal_pc.challenge_id, device_id="pc-01", pin_code=chal_pc.pin_code, user_confirmed=True))
    presence.update_heartbeat("pc-01")

    # Register Phone
    phone_req = PairingRequest(
        device_id="phone-01",
        device_name="Pixel Mobile",
        device_role=DeviceRole.MOBILE_NODE,
        capabilities=[DeviceCapability.ANDROID_CONTROL, DeviceCapability.MICROPHONE, DeviceCapability.BATTERY],
        public_key_pem="pem-phone",
    )
    chal_phone = registry.initiate_pairing(phone_req)
    registry.complete_pairing(PairingConfirmation(challenge_id=chal_phone.challenge_id, device_id="phone-01", pin_code=chal_phone.pin_code, user_confirmed=True))
    presence.update_heartbeat("phone-01")

    handoff = HandoffManager(registry=registry, presence=presence)
    return registry, presence, handoff


def test_context_handoff_and_sanitization() -> None:
    _, _, handoff = _setup_environment()

    raw_context = {
        "user_query": "Summarize my meetings",
        "recent_dialog": ["Hello Pixel", "Here are your meetings"],
        "auth_token": "SUPER_SECRET_BEARER_TOKEN",
        "api_key": "sk-123456789",
        "nested": {
            "safe_data": "value",
            "password": "my_password",
        },
    }

    ctx_payload = handoff.initiate_context_handoff(
        source_device_id="phone-01",
        target_device_id="pc-01",
        session_id="session-42",
        conversation_context=raw_context,
        active_language="en",
    )

    assert ctx_payload.source_device_id == "phone-01"
    assert ctx_payload.target_device_id == "pc-01"
    assert "user_query" in ctx_payload.conversation_context
    # Verify sensitive keys are stripped
    assert "auth_token" not in ctx_payload.conversation_context
    assert "api_key" not in ctx_payload.conversation_context
    assert "password" not in ctx_payload.conversation_context["nested"]
    assert ctx_payload.conversation_context["nested"]["safe_data"] == "value"


def test_task_handoff_concurrency_lease() -> None:
    _, _, handoff = _setup_environment()

    task_payload = handoff.initiate_task_handoff(
        source_device_id="phone-01",
        target_device_id="pc-01",
        task_id="task-99",
        current_version=1,
        plan_steps=[{"step": 1, "description": "Run tests"}],
        current_step_index=0,
        required_capability=DeviceCapability.DESKTOP_CONTROL,
    )

    assert task_payload.task_id == "task-99"
    assert task_payload.task_version == 2
    assert len(task_payload.concurrency_lease_token) > 20

    # Target completes handoff successfully with matching token
    ok = handoff.complete_task_handoff(
        task_id="task-99",
        target_device_id="pc-01",
        lease_token=task_payload.concurrency_lease_token,
    )
    assert ok is True

    # Bad token fails
    bad_ok = handoff.complete_task_handoff(
        task_id="task-99",
        target_device_id="pc-01",
        lease_token="invalid-token",
    )
    assert bad_ok is False


def test_task_handoff_capability_mismatch_fails() -> None:
    _, _, handoff = _setup_environment()

    # Attempting to migrate a DESKTOP_CONTROL task to phone-01 (which lacks it)
    with pytest.raises(ValueError, match="lacks required capability"):
        handoff.initiate_task_handoff(
            source_device_id="pc-01",
            target_device_id="phone-01",
            task_id="task-desktop-only",
            current_version=1,
            plan_steps=[],
            required_capability=DeviceCapability.DESKTOP_CONTROL,
        )


def test_task_handoff_offline_target_fails() -> None:
    _, presence, handoff = _setup_environment()
    presence.set_device_offline("pc-01")

    with pytest.raises(RuntimeError, match="not currently online"):
        handoff.initiate_task_handoff(
            source_device_id="phone-01",
            target_device_id="pc-01",
            task_id="task-100",
            current_version=1,
            plan_steps=[],
        )

