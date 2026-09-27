"""Unit tests for MockAndroidDeviceRuntime and simulated Android assistant lifecycle."""

import pytest

from packages.contracts.mobile import MobileAssistantState
from services.voice_gateway.mobile_adapter import MobileGatewayAdapter
from services.voice_gateway.mock_mobile_device import MockAndroidDeviceRuntime


@pytest.mark.asyncio
async def test_mock_device_lifecycle_and_registration() -> None:
    adapter = MobileGatewayAdapter()
    device = MockAndroidDeviceRuntime(adapter=adapter)

    initial_state = device.state
    assert initial_state == MobileAssistantState.UNINITIALIZED

    # 1. Connect and Register
    res = await device.connect_to_gateway()
    assert res.success is True
    assert device.active_session_id is not None
    assert device.state == MobileAssistantState.READY


@pytest.mark.asyncio
async def test_mock_device_role_and_permissions() -> None:
    device = MockAndroidDeviceRuntime()

    # Request Role
    assert device.request_assistant_role(grant=True) is True
    assert device.is_default_assistant is True

    # Request Mic Permission
    assert device.request_microphone_permission(grant=True) is True
    assert device.has_mic_permission is True

    # Foreground service startup
    assert device.start_foreground_service() is True
    assert device.is_foreground_service_running is True


@pytest.mark.asyncio
async def test_mock_device_wake_audio_and_barge_in() -> None:
    adapter = MobileGatewayAdapter()
    device = MockAndroidDeviceRuntime(adapter=adapter)
    await device.connect_to_gateway()

    # Trigger wake word
    assert await device.trigger_wake_phrase("hey pixel") is True
    assert device.state == MobileAssistantState.PROCESSING

    # Stream audio frame (16kHz mono dummy frame)
    dummy_pcm = b"\x00\x00" * 320
    audio_res = await device.stream_audio_chunk(dummy_pcm)
    assert audio_res["status"] == "processed"
    assert audio_res["bytes_received"] == len(dummy_pcm)

    # Barge-in interruption
    device.state = MobileAssistantState.SPEAKING
    barge_res = await device.send_barge_in_interruption()
    assert barge_res["status"] == "interrupted"
    assert device.state == MobileAssistantState.LISTENING
