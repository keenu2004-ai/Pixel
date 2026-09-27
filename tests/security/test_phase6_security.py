"""Hostile Security, Mobile Channel, and Authentication Defense Tests for Phase 6."""

import pytest

from packages.contracts.mobile import (
    MobileApprovalResponse,
    MobileAssistantState,
    MobileDeviceMetadata,
    MobileRegistrationRequest,
    MobileVoicePacket,
)
from services.voice_gateway.mobile_adapter import MobileGatewayAdapter
from services.voice_gateway.mock_mobile_device import MockAndroidDeviceRuntime


@pytest.mark.asyncio
async def test_mobile_unauthorized_token_rejection() -> None:
    adapter = MobileGatewayAdapter(shared_auth_secret="correct_secret_key_999")

    attack_payloads = [
        "",
        "admin",
        "Bearer invalid",
        "../../etc/passwd",
        "' OR '1'='1",
        "CORRECT_SECRET_KEY_999",  # case-sensitive check
    ]

    for bad_token in attack_payloads:
        req = MobileRegistrationRequest(
            device_id="attacker_device",
            auth_token=bad_token,
            device_metadata=MobileDeviceMetadata(device_id="attacker_device"),
        )
        res = await adapter.register_device(req)
        assert res.success is False
        assert "Authentication failed" in (res.error_message or "")


@pytest.mark.asyncio
async def test_mobile_approval_tampering_and_replay_rejected() -> None:
    adapter = MobileGatewayAdapter(shared_auth_secret="sec_key")

    card = adapter.dispatch_approval_request(
        task_id="task_sec_1",
        tool_name="drop_table",
        risk_class="HIGH_IMPACT",
        reason="Security test",
        confirmation_token="legit_token_123",
        arguments={"table": "users"},
    )

    # 1. Tampering confirmation token
    tampered_resp = MobileApprovalResponse(
        approval_id=card.approval_id,
        task_id=card.task_id,
        confirmation_token="tampered_token_456",
        user_approved=True,
    )
    ok, err = adapter.process_approval_response(tampered_resp)
    assert ok is False
    assert "token mismatch" in (err or "").lower()

    # 2. Legitimate consumption
    legit_resp = MobileApprovalResponse(
        approval_id=card.approval_id,
        task_id=card.task_id,
        confirmation_token="legit_token_123",
        user_approved=True,
    )
    ok_legit, err_legit = adapter.process_approval_response(legit_resp)
    assert ok_legit is True
    assert err_legit is None

    # 3. Replay attack with the exact same response (card should be consumed already)
    ok_replay, err_replay = adapter.process_approval_response(legit_resp)
    assert ok_replay is False
    assert "not found or expired" in (err_replay or "").lower()


def test_state_machine_illegal_transition_rejection() -> None:
    device = MockAndroidDeviceRuntime()
    assert device.state == MobileAssistantState.UNINITIALIZED

    # Cannot jump to SPEAKING or AWAITING_APPROVAL from UNINITIALIZED
    assert device.transition_to(MobileAssistantState.SPEAKING) is False
    assert device.transition_to(MobileAssistantState.AWAITING_APPROVAL) is False
    assert device.transition_to(MobileAssistantState.PROCESSING) is False
    assert device.state == MobileAssistantState.UNINITIALIZED


@pytest.mark.asyncio
async def test_voice_packet_without_session_rejected() -> None:
    adapter = MobileGatewayAdapter()

    packet = MobileVoicePacket(
        session_id="nonexistent_session_id_999",
        event_type="audio_frame",
        pcm_base64="AAAA",
    )
    res = await adapter.handle_voice_packet(packet)
    assert res["status"] == "error"
    assert "not found" in res["message"]
