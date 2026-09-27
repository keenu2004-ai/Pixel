"""Typed contracts and data models for Phase 10 Production Hardening & Full-Stack Control Plane."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.contracts.autonomous import (
    MissedJobPolicy,
    ScheduleType,
    TaskLifecycleState,
)
from packages.contracts.events import VoiceState


def _generate_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UserRole(StrEnum):
    """Role-Based Access Control tiers for PIXEL Control Plane."""

    READ_ONLY = "READ_ONLY"
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"
    SYSTEM = "SYSTEM"


class UserIdentity(BaseModel):
    """Authenticated user profile within Control Plane."""

    user_id: str
    username: str
    role: UserRole
    created_at: datetime = Field(default_factory=_utc_now)
    last_login: datetime | None = None
    is_active: bool = True


class LoginRequest(BaseModel):
    """Authentication request payload."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Authentication response returning bearer token and user metadata."""

    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int = 3600
    user: UserIdentity


class TokenPayload(BaseModel):
    """Decoded JWT / session token payload."""

    sub: str  # user_id
    username: str
    role: UserRole
    exp: int
    iat: int
    jti: str = Field(default_factory=_generate_id)


class ServiceHealthStatus(BaseModel):
    """Health indicator for an individual PIXEL subsystem."""

    service_name: str
    is_healthy: bool
    latency_ms: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)


class SystemOverview(BaseModel):
    """Authoritative real-time system state and health overview."""

    runtime_version: str = "1.0.0"
    environment: str = "production"
    is_online: bool = True
    active_devices_count: int = 0
    active_tasks_count: int = 0
    active_sessions_count: int = 0
    services: list[ServiceHealthStatus] = Field(default_factory=list)
    resource_stats: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)


class ConversationSessionView(BaseModel):
    """Real-time operational view of an active or recent conversation session."""

    session_id: str
    user_id: str
    device_id: str
    voice_state: VoiceState = VoiceState.IDLE
    current_transcript: str = ""
    last_response: str = ""
    turn_count: int = 0
    recent_turns: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    last_activity: datetime = Field(default_factory=_utc_now)


class TaskSummary(BaseModel):
    """Summary representation of an autonomous task for dashboard tables."""

    task_id: str
    user_id: str
    objective: str
    state: TaskLifecycleState
    schedule_type: ScheduleType
    schedule_expr: str | None = None
    created_at: datetime
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    budget_consumed_steps: int = 0
    budget_max_steps: int = 20
    is_paused: bool = False
    is_cancelled: bool = False
    failure_reason: str | None = None


class TaskActionRequest(BaseModel):
    """Control plane command sent to mutate an autonomous task."""

    action: str  # "PAUSE", "RESUME", "CANCEL", "APPROVE", "REJECT", "TRIGGER_NOW"
    reason: str = "Operator action from Control Plane"
    confirmation_token: str | None = None  # For approving high-impact actions
    arguments: dict[str, Any] = Field(default_factory=dict)


class TaskActionResponse(BaseModel):
    """Response from executing a task action."""

    success: bool
    task_id: str
    action: str
    new_state: TaskLifecycleState
    message: str


class CreateTaskRequest(BaseModel):
    """Request payload to create and schedule a new autonomous task."""

    objective: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    allowed_targets: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    schedule_type: ScheduleType = ScheduleType.ONE_SHOT
    schedule_expr: str | None = None
    missed_job_policy: MissedJobPolicy = MissedJobPolicy.EXECUTE_ONCE_NEXT_AVAILABLE
    max_steps: int = 20
    max_tool_calls: int = 15
    max_duration_seconds: float = 300.0
    allowed_tools: list[str] = Field(default_factory=list)
    prohibited_tools: list[str] = Field(default_factory=list)


class MemoryFactView(BaseModel):
    """View of a persistent semantic fact stored in memory."""

    fact_id: str
    user_id: str
    category: str
    key: str
    value: Any
    confidence: float
    provenance: str
    created_at: datetime


class MemoryEpisodeView(BaseModel):
    """View of an episodic interaction turn in memory."""

    episode_id: str
    session_id: str
    user_id: str
    user_query: str
    assistant_response: str
    created_at: datetime


class MemoryPurgeRequest(BaseModel):
    """Request to delete memory records under Right to Forget."""

    keyword: str
    user_id: str = "default_user"


class DeviceActionRequest(BaseModel):
    """Action requested on a device node."""

    action: str  # "REVOKE", "REMOVE", "PING", "SET_OFFLINE"
    reason: str = "Admin requested from Control Plane"


class ControlPlaneEventType(StrEnum):
    """Realtime stream event types emitted across the Control Plane WebSocket."""

    SYSTEM_STATE = "SYSTEM_STATE"
    CONVERSATION_UPDATE = "CONVERSATION_UPDATE"
    TASK_STATE_CHANGED = "TASK_STATE_CHANGED"
    SCHEDULER_TICK = "SCHEDULER_TICK"
    DEVICE_PRESENCE = "DEVICE_PRESENCE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    AUDIT_EVENT = "AUDIT_EVENT"
    ERROR_ALERT = "ERROR_ALERT"


class ControlPlaneStreamEvent(BaseModel):
    """Typed WebSocket event frame pushed to connected Control Plane clients."""

    event_id: str = Field(default_factory=_generate_id)
    event_type: ControlPlaneEventType
    timestamp: datetime = Field(default_factory=_utc_now)
    payload: dict[str, Any] = Field(default_factory=dict)
