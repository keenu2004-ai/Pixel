"""Unit tests for Mobile Assistant, Device Metadata, and Transport Contracts."""

from packages.contracts.mobile import (
    MobileApprovalRequest,
    MobileApprovalResponse,
    MobileAssistantState,
    MobileDeviceMetadata,
    MobileRegistrationRequest,
    MobileRegistrationResponse,
)


def test_mobile_assistant_states() -> None:
    assert MobileAssistantState.UNINITIALIZED == "UNINITIALIZED"
    assert MobileAssistantState.LISTENING == "LISTENING"
    assert MobileAssistantState.WAKE_DETECTED == "WAKE_DETECTED"
    assert MobileAssistantState.AWAITING_APPROVAL == "AWAITING_APPROVAL"


def test_mobile_device_metadata_validation() -> None:
    meta = MobileDeviceMetadata(
        device_id="pixel_8_pro_test",
        model="Pixel 8 Pro",
        api_level=34,
        battery_level=88,
        is_charging=True,
        is_default_assistant=True,
    )
    assert meta.device_id == "pixel_8_pro_test"
    assert meta.api_level == 34
    assert meta.is_default_assistant is True


def test_mobile_registration_contracts() -> None:
    req = MobileRegistrationRequest(
        device_id="device_123",
        auth_token="secret_token",
        device_metadata=MobileDeviceMetadata(device_id="device_123"),
        preferred_language="hi",
    )
    assert req.preferred_language == "hi"

    res = MobileRegistrationResponse(
        success=True,
        session_id="session_xyz",
        websocket_url="/ws/voice",
    )
    assert res.success is True
    assert res.session_id == "session_xyz"


def test_mobile_approval_exchange_contracts() -> None:
    req = MobileApprovalRequest(
        approval_id="appr_001",
        task_id="task_001",
        tool_name="delete_database",
        risk_class="HIGH_IMPACT",
        reason="Requires user confirmation",
        confirmation_token="hmac_token_123",
    )
    assert req.approval_id == "appr_001"

    res = MobileApprovalResponse(
        approval_id="appr_001",
        task_id="task_001",
        confirmation_token="hmac_token_123",
        user_approved=True,
        biometric_authenticated=True,
    )
    assert res.user_approved is True
    assert res.biometric_authenticated is True
