"""Unit tests for MobileGatewayAdapter registration, voice packet dispatch, and approvals."""

import pytest

from packages.contracts.mobile import (
    MobileApprovalResponse,
    MobileDeviceMetadata,
    MobileRegistrationRequest,
)
from services.voice_gateway.mobile_adapter import MobileGatewayAdapter


@pytest.mark.asyncio
async def test_adapter_registration_valid_and_invalid_token() -> None:
    adapter = MobileGatewayAdapter(shared_auth_secret="test_secret_123")

    meta = MobileDeviceMetadata(device_id="dev_001")

    # 1. Invalid Token Rejection
    bad_req = MobileRegistrationRequest(
        device_id="dev_001",
        auth_token="wrong_token",
        device_metadata=meta,
    )
    bad_res = await adapter.register_device(bad_req)
    assert bad_res.success is False
    assert "Authentication failed" in (bad_res.error_message or "")

    # 2. Valid Token Success
    good_req = MobileRegistrationRequest(
        device_id="dev_001",
        auth_token="test_secret_123",
        device_metadata=meta,
    )
    good_res = await adapter.register_device(good_req)
    assert good_res.success is True
    assert good_res.session_id is not None
    assert "dev_001" in adapter.registered_devices


@pytest.mark.asyncio
async def test_adapter_approval_dispatch_and_validation() -> None:
    adapter = MobileGatewayAdapter(shared_auth_secret="test_secret_123")

    # Dispatch Approval
    card = adapter.dispatch_approval_request(
        task_id="task_100",
        tool_name="delete_file",
        risk_class="HIGH_IMPACT",
        reason="Requires confirmation",
        confirmation_token="valid_hmac_token_xyz",
        arguments={"path": "important.txt"},
    )
    assert card.approval_id in adapter.pending_mobile_approvals

    # Valid Approval Response
    good_resp = MobileApprovalResponse(
        approval_id=card.approval_id,
        task_id=card.task_id,
        confirmation_token="valid_hmac_token_xyz",
        user_approved=True,
    )
    ok, err = adapter.process_approval_response(good_resp)
    assert ok is True
    assert err is None
    assert card.approval_id not in adapter.pending_mobile_approvals
