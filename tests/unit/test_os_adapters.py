"""Unit tests for OS Capability Adapters (Mock & Windows)."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from packages.contracts.errors import ToolExecutionException
from services.os_control.mock_adapter import MockOSAdapter
from services.os_control.windows_adapter import WindowsOSAdapter


class TestMockOSAdapter:
    """Tests for MockOSAdapter."""

    @pytest.mark.asyncio
    async def test_timer_lifecycle(self) -> None:
        adapter = MockOSAdapter()
        t = await adapter.set_timer(duration_seconds=60, label="Tea timer")
        assert t["duration_seconds"] == 60
        assert t["label"] == "Tea timer"
        assert t["status"] == "RUNNING"

        status = await adapter.get_timer_status(t["timer_id"])
        assert status["status"] == "RUNNING"

        cancelled = await adapter.cancel_timer(t["timer_id"])
        assert cancelled is True
        status_after = await adapter.get_timer_status(t["timer_id"])
        assert status_after["status"] == "CANCELLED"

    @pytest.mark.asyncio
    async def test_alarm_lifecycle(self) -> None:
        adapter = MockOSAdapter()
        target = datetime.now(UTC) + timedelta(hours=8)
        alarm = await adapter.set_alarm(target_time=target, label="Wake up")
        assert alarm["label"] == "Wake up"

        alarms = await adapter.list_alarms()
        assert len(alarms) == 1
        assert alarms[0]["alarm_id"] == alarm["alarm_id"]

        cancelled = await adapter.cancel_alarm(alarm["alarm_id"])
        assert cancelled is True
        assert len(await adapter.list_alarms()) == 0

    @pytest.mark.asyncio
    async def test_reminder_lifecycle(self) -> None:
        adapter = MockOSAdapter()
        target = datetime.now(UTC) + timedelta(hours=2)
        rem = await adapter.set_reminder(text="Buy groceries", target_time=target)
        assert rem["text"] == "Buy groceries"

        rems = await adapter.list_reminders()
        assert len(rems) == 1

        cancelled = await adapter.cancel_reminder(rem["reminder_id"])
        assert cancelled is True
        assert len(await adapter.list_reminders()) == 0

    @pytest.mark.asyncio
    async def test_volume_controls(self) -> None:
        adapter = MockOSAdapter()
        assert await adapter.set_volume(75) == 75
        assert await adapter.adjust_volume(-10) == 65
        assert await adapter.mute_volume() is True
        assert adapter.is_muted is True
        assert await adapter.unmute_volume() is True
        assert adapter.is_muted is False

    @pytest.mark.asyncio
    async def test_app_lifecycle(self) -> None:
        adapter = MockOSAdapter()
        assert await adapter.launch_app("chrome") is True
        assert "chrome" in adapter.running_apps
        assert await adapter.close_app("chrome") is True
        assert "chrome" not in adapter.running_apps


class TestWindowsOSAdapter:
    """Tests for WindowsOSAdapter."""

    @pytest.mark.asyncio
    async def test_persistence_alarms_and_reminders(self, tmp_path: Path) -> None:
        adapter = WindowsOSAdapter(persistence_dir=str(tmp_path))

        target = datetime.now(UTC) + timedelta(days=1)
        alarm = await adapter.set_alarm(target_time=target, label="Work meeting")
        alarms = await adapter.list_alarms()
        assert len(alarms) == 1
        assert alarms[0]["label"] == "Work meeting"

        # Verify disk persistence across adapter re-instantiation
        adapter2 = WindowsOSAdapter(persistence_dir=str(tmp_path))
        alarms2 = await adapter2.list_alarms()
        assert len(alarms2) == 1
        assert alarms2[0]["alarm_id"] == alarm["alarm_id"]

        # Cancel alarm
        assert await adapter2.cancel_alarm(alarm["alarm_id"]) is True
        assert len(await adapter2.list_alarms()) == 0

    @pytest.mark.asyncio
    async def test_unapproved_app_launch_rejected(self, tmp_path: Path) -> None:
        adapter = WindowsOSAdapter(persistence_dir=str(tmp_path))
        with pytest.raises(ToolExecutionException) as exc_info:
            await adapter.launch_app("dangerous_unapproved_malware.exe")
        assert "not in the approved whitelist" in str(exc_info.value)
