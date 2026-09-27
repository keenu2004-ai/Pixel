"""Abstract Interface for OS Capability Adapters."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class BaseOSAdapter(ABC):
    """Abstract interface for platform-specific OS interactions."""

    # 1. Timers
    @abstractmethod
    async def set_timer(self, duration_seconds: int, label: str = "Timer") -> dict[str, Any]:
        """Starts an asynchronous timer."""
        pass

    @abstractmethod
    async def cancel_timer(self, timer_id: str | None = None) -> bool:
        """Cancels an active timer."""
        pass

    @abstractmethod
    async def get_timer_status(self, timer_id: str | None = None) -> dict[str, Any]:
        """Queries the remaining time of an active timer."""
        pass

    # 2. Alarms
    @abstractmethod
    async def set_alarm(
        self,
        target_time: datetime,
        label: str = "Alarm",
        repeat: str | None = None,
    ) -> dict[str, Any]:
        """Schedules a persistent alarm."""
        pass

    @abstractmethod
    async def cancel_alarm(self, alarm_id: str | None = None) -> bool:
        """Cancels an alarm."""
        pass

    @abstractmethod
    async def list_alarms(self) -> list[dict[str, Any]]:
        """Returns all scheduled alarms."""
        pass

    # 3. Reminders
    @abstractmethod
    async def set_reminder(self, text: str, target_time: datetime) -> dict[str, Any]:
        """Schedules a persistent reminder."""
        pass

    @abstractmethod
    async def list_reminders(self) -> list[dict[str, Any]]:
        """Returns all active reminders."""
        pass

    @abstractmethod
    async def cancel_reminder(self, reminder_id: str | None = None) -> bool:
        """Cancels a reminder."""
        pass

    # 4. Volume / Audio
    @abstractmethod
    async def set_volume(self, level: int) -> int:
        """Sets the system master volume level (0-100)."""
        pass

    @abstractmethod
    async def adjust_volume(self, delta: int) -> int:
        """Adjusts master volume up or down by delta."""
        pass

    @abstractmethod
    async def mute_volume(self) -> bool:
        """Mutes system audio."""
        pass

    @abstractmethod
    async def unmute_volume(self) -> bool:
        """Unmutes system audio."""
        pass

    # 5. Application Lifecycle
    @abstractmethod
    async def launch_app(self, app_name: str, parameters: list[str] | None = None) -> bool:
        """Launches a whitelisted application."""
        pass

    @abstractmethod
    async def close_app(self, app_name: str) -> bool:
        """Closes an active application."""
        pass

    # 6. System Queries
    @abstractmethod
    async def get_system_time(self) -> datetime:
        """Queries current system time."""
        pass

    @abstractmethod
    async def get_battery_status(self) -> dict[str, Any]:
        """Queries system battery status."""
        pass
