"""Deterministic Intent Contracts for Phase 2.

Defines strongly-typed data structures for alarms, timers, reminders, volume,
app launching, and system queries.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex[:12]


class AlarmAction(StrEnum):
    SET = "SET"
    CANCEL = "CANCEL"
    LIST = "LIST"


class TimerAction(StrEnum):
    SET = "SET"
    CANCEL = "CANCEL"
    STATUS = "STATUS"


class ReminderAction(StrEnum):
    SET = "SET"
    CANCEL = "CANCEL"
    LIST = "LIST"


class VolumeAction(StrEnum):
    SET = "SET"
    MUTE = "MUTE"
    UNMUTE = "UNMUTE"
    INCREASE = "INCREASE"
    DECREASE = "DECREASE"


class AppAction(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class SystemQueryType(StrEnum):
    TIME = "TIME"
    DATE = "DATE"
    BATTERY = "BATTERY"
    STATUS = "STATUS"


class AlarmIntentData(BaseModel):
    """Payload for alarm operations."""

    action: AlarmAction = Field(default=AlarmAction.SET)
    alarm_id: str = Field(default_factory=_gen_id)
    time_str: str | None = Field(default=None, description="Raw or parsed time string")
    target_time: datetime | None = Field(
        default=None, description="Resolved target alarm timestamp"
    )
    label: str = Field(default="Alarm", description="Optional label for the alarm")
    repeat: str | None = Field(default=None, description="Repeat pattern (e.g. weekdays, daily)")


class TimerIntentData(BaseModel):
    """Payload for timer operations."""

    action: TimerAction = Field(default=TimerAction.SET)
    timer_id: str = Field(default_factory=_gen_id)
    duration_seconds: int = Field(default=0, ge=0, le=86400, description="Duration in seconds")
    label: str = Field(default="Timer", description="Optional label for the timer")


class ReminderIntentData(BaseModel):
    """Payload for reminder operations."""

    action: ReminderAction = Field(default=ReminderAction.SET)
    reminder_id: str = Field(default_factory=_gen_id)
    text: str = Field(..., description="Content of the reminder")
    target_time: datetime | None = Field(default=None, description="Resolved reminder timestamp")


class VolumeIntentData(BaseModel):
    """Payload for media and volume controls."""

    action: VolumeAction = Field(...)
    level: int | None = Field(
        default=None, ge=0, le=100, description="Target volume percentage (0-100)"
    )
    step: int = Field(default=10, ge=1, le=50, description="Increment/decrement step percentage")


class AppLaunchIntentData(BaseModel):
    """Payload for application launching."""

    action: AppAction = Field(default=AppAction.OPEN)
    app_name: str = Field(..., description="Canonical or requested application name")
    parameters: list[str] = Field(default_factory=list, description="Sanitized CLI arguments")


class SystemQueryIntentData(BaseModel):
    """Payload for system time, date, battery, or status query."""

    query_type: SystemQueryType = Field(...)
    details: dict[str, Any] = Field(default_factory=dict)
