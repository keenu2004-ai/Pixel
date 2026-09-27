"""Unit tests for AndroidActionAdapter."""

import pytest

from packages.contracts.mobile import (
    AndroidActionPayload,
    AndroidActionType,
)
from services.voice_gateway.android_actions import AndroidActionAdapter


@pytest.mark.asyncio
async def test_android_call_exact_contact() -> None:
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.CALL,
        parameters={"contact_name": "Mom"},
    )
    result = await adapter.execute_action(payload)
    assert result.success
    assert result.state_verified
    assert result.result_data.get("phone_number") == "+91-9876543210"


@pytest.mark.asyncio
async def test_android_call_ambiguous_contact() -> None:
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.CALL,
        parameters={"contact_name": "Rahul"},
    )
    result = await adapter.execute_action(payload)
    # Ambiguous contact match must be flagged and not blindly dialed
    assert not result.success
    assert "Ambiguous contact matches" in (result.error_message or "")
    assert len(result.result_data.get("candidates", [])) == 2


@pytest.mark.asyncio
async def test_android_sms_action() -> None:
    adapter = AndroidActionAdapter()
    payload = AndroidActionPayload(
        action_type=AndroidActionType.SMS,
        parameters={"recipient": "Mom", "message": "I'm reaching in 20 minutes."},
    )
    result = await adapter.execute_action(payload)
    assert result.success
    assert result.state_verified
    assert result.result_data.get("message") == "I'm reaching in 20 minutes."


@pytest.mark.asyncio
async def test_android_alarm_and_timer() -> None:
    adapter = AndroidActionAdapter()

    # Alarm
    alarm_payload = AndroidActionPayload(
        action_type=AndroidActionType.ALARM,
        parameters={"hour": 7, "minutes": 0, "message": "Wake up"},
    )
    res_alarm = await adapter.execute_action(alarm_payload)
    assert res_alarm.success
    assert res_alarm.state_verified

    # Timer
    timer_payload = AndroidActionPayload(
        action_type=AndroidActionType.TIMER,
        parameters={"duration_seconds": 300, "label": "Tea Timer"},
    )
    res_timer = await adapter.execute_action(timer_payload)
    assert res_timer.success
    assert res_timer.state_verified


@pytest.mark.asyncio
async def test_android_media_and_calendar() -> None:
    adapter = AndroidActionAdapter()

    # Media
    media_payload = AndroidActionPayload(
        action_type=AndroidActionType.MEDIA_CONTROL,
        parameters={"command": "SET_VOLUME", "volume": 75},
    )
    res_media = await adapter.execute_action(media_payload)
    assert res_media.success
    assert res_media.result_data.get("volume") == 75

    # Calendar
    cal_payload = AndroidActionPayload(
        action_type=AndroidActionType.CALENDAR,
        parameters={
            "title": "Team Standup",
            "start_time_iso": "2026-09-28T10:00:00Z",
            "end_time_iso": "2026-09-28T10:30:00Z",
        },
    )
    res_cal = await adapter.execute_action(cal_payload)
    assert res_cal.success
    assert res_cal.state_verified
