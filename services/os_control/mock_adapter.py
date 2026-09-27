"""Deterministic In-Memory Mock OS Adapter.

Provides fast, reproducible OS capability execution for testing and non-Windows environments.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from packages.core.interfaces.os_adapter import BaseOSAdapter

logger = logging.getLogger(__name__)


class MockOSAdapter(BaseOSAdapter):
    """In-memory deterministic OS adapter."""

    def __init__(self) -> None:
        self.timers: dict[str, dict[str, Any]] = {}
        self.alarms: dict[str, dict[str, Any]] = {}
        self.reminders: dict[str, dict[str, Any]] = {}
        self.current_volume: int = 50
        self.is_muted: bool = False
        self.running_apps: set[str] = set()

    # 1. Timers
    async def set_timer(self, duration_seconds: int, label: str = "Timer") -> dict[str, Any]:
        timer_id = f"tmr_{uuid4().hex[:8]}"
        created_at = datetime.now(UTC)
        entry = {
            "timer_id": timer_id,
            "duration_seconds": duration_seconds,
            "label": label,
            "created_at": created_at.isoformat(),
            "remaining_seconds": duration_seconds,
            "status": "RUNNING",
        }
        self.timers[timer_id] = entry
        logger.info("Mock timer set: %s (%ss)", timer_id, duration_seconds)
        return entry

    async def cancel_timer(self, timer_id: str | None = None) -> bool:
        if timer_id and timer_id in self.timers:
            self.timers[timer_id]["status"] = "CANCELLED"
            return True
        elif self.timers:
            # Cancel most recent
            latest_id = list(self.timers.keys())[-1]
            self.timers[latest_id]["status"] = "CANCELLED"
            return True
        return False

    async def get_timer_status(self, timer_id: str | None = None) -> dict[str, Any]:
        if timer_id and timer_id in self.timers:
            return self.timers[timer_id]
        if self.timers:
            return list(self.timers.values())[-1]
        return {"status": "NO_ACTIVE_TIMER", "remaining_seconds": 0}

    # 2. Alarms
    async def set_alarm(
        self,
        target_time: datetime,
        label: str = "Alarm",
        repeat: str | None = None,
    ) -> dict[str, Any]:
        alarm_id = f"alm_{uuid4().hex[:8]}"
        entry = {
            "alarm_id": alarm_id,
            "target_time": target_time.isoformat(),
            "label": label,
            "repeat": repeat,
            "status": "ACTIVE",
        }
        self.alarms[alarm_id] = entry
        logger.info("Mock alarm scheduled: %s at %s", alarm_id, target_time)
        return entry

    async def cancel_alarm(self, alarm_id: str | None = None) -> bool:
        if alarm_id and alarm_id in self.alarms:
            del self.alarms[alarm_id]
            return True
        elif self.alarms:
            latest_id = list(self.alarms.keys())[-1]
            del self.alarms[latest_id]
            return True
        return False

    async def list_alarms(self) -> list[dict[str, Any]]:
        return list(self.alarms.values())

    # 3. Reminders
    async def set_reminder(self, text: str, target_time: datetime) -> dict[str, Any]:
        reminder_id = f"rem_{uuid4().hex[:8]}"
        entry = {
            "reminder_id": reminder_id,
            "text": text,
            "target_time": target_time.isoformat(),
            "status": "PENDING",
        }
        self.reminders[reminder_id] = entry
        logger.info("Mock reminder scheduled: %s for %s", reminder_id, target_time)
        return entry

    async def list_reminders(self) -> list[dict[str, Any]]:
        return list(self.reminders.values())

    async def cancel_reminder(self, reminder_id: str | None = None) -> bool:
        if reminder_id and reminder_id in self.reminders:
            del self.reminders[reminder_id]
            return True
        elif self.reminders:
            latest_id = list(self.reminders.keys())[-1]
            del self.reminders[latest_id]
            return True
        return False

    # 4. Volume
    async def set_volume(self, level: int) -> int:
        self.current_volume = max(0, min(100, level))
        self.is_muted = False
        return self.current_volume

    async def adjust_volume(self, delta: int) -> int:
        return await self.set_volume(self.current_volume + delta)

    async def mute_volume(self) -> bool:
        self.is_muted = True
        return True

    async def unmute_volume(self) -> bool:
        self.is_muted = False
        return True

    # 5. Apps
    async def launch_app(self, app_name: str, parameters: list[str] | None = None) -> bool:
        self.running_apps.add(app_name.lower().strip())
        logger.info("Mock app launched: %s", app_name)
        return True

    async def close_app(self, app_name: str) -> bool:
        name = app_name.lower().strip()
        if name in self.running_apps:
            self.running_apps.remove(name)
            return True
        return False

    # 6. System Queries
    async def get_system_time(self) -> datetime:
        return datetime.now(UTC)

    async def get_battery_status(self) -> dict[str, Any]:
        return {"percentage": 85, "is_charging": True, "power_source": "AC"}
