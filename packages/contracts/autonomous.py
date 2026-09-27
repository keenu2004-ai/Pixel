"""Typed contracts and domain models for Phase 9 Proactive & Autonomous Workflows."""

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TaskLifecycleState(StrEnum):
    """Lifecycle states for autonomous tasks."""

    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    AUTHORIZED = "AUTHORIZED"
    SCHEDULED = "SCHEDULED"
    RUNNING = "RUNNING"
    CHECKPOINTING = "CHECKPOINTING"
    VERIFYING = "VERIFYING"
    DRIFT_CHECK = "DRIFT_CHECK"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    DRIFT_DETECTED = "DRIFT_DETECTED"
    POLICY_DENIED = "POLICY_DENIED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ScheduleType(StrEnum):
    """Scheduling trigger strategies."""

    ONE_SHOT = "ONE_SHOT"
    INTERVAL = "INTERVAL"
    CRON = "CRON"
    EVENT_DRIVEN = "EVENT_DRIVEN"


class MissedJobPolicy(StrEnum):
    """Policy when a scheduled job was missed due to downtime."""

    EXECUTE_ONCE_NEXT_AVAILABLE = "EXECUTE_ONCE_NEXT_AVAILABLE"
    SKIP = "SKIP"
    RESCHEDULE = "RESCHEDULE"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class GoalContract(BaseModel):
    """Immutable contract defining the authorized objective and constraints of an autonomous task."""

    objective: str
    success_criteria: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    allowed_targets: list[str] = Field(default_factory=list)
    prohibited_actions: list[str] = Field(default_factory=list)
    expiration: datetime | None = None
    authorized_by: str = "user_primary"


class ExecutionBudget(BaseModel):
    """Finite operational resource budget for autonomous execution."""

    max_steps: int = 20
    max_tool_calls: int = 15
    max_duration_seconds: float = 300.0
    max_retries: int = 3
    max_tokens: int = 10000

    consumed_steps: int = 0
    consumed_tool_calls: int = 0
    consumed_duration_seconds: float = 0.0
    consumed_retries: int = 0
    consumed_tokens: int = 0

    def is_exceeded(self) -> tuple[bool, str | None]:
        """Check if any budget dimension has been breached."""
        if self.consumed_steps >= self.max_steps:
            return True, f"Step budget exceeded: {self.consumed_steps}/{self.max_steps}"
        if self.consumed_tool_calls >= self.max_tool_calls:
            return (
                True,
                f"Tool call budget exceeded: {self.consumed_tool_calls}/{self.max_tool_calls}",
            )
        if self.consumed_duration_seconds >= self.max_duration_seconds:
            return (
                True,
                f"Duration budget exceeded: {self.consumed_duration_seconds:.1f}s/{self.max_duration_seconds:.1f}s",
            )
        if self.consumed_retries >= self.max_retries:
            return True, f"Retry budget exceeded: {self.consumed_retries}/{self.max_retries}"
        if self.consumed_tokens >= self.max_tokens:
            return True, f"Token budget exceeded: {self.consumed_tokens}/{self.max_tokens}"
        return False, None


class DriftPolicy(BaseModel):
    """Policy parameters for autonomous goal drift detection."""

    max_divergence_score: float = 0.5
    allow_target_expansion: bool = False
    allow_tool_category_expansion: bool = False
    pause_on_drift: bool = True


class NotificationPolicy(BaseModel):
    """Notification dispatch preferences for autonomous tasks."""

    notify_on_start: bool = False
    notify_on_complete: bool = True
    notify_on_failure: bool = True
    notify_on_drift: bool = True
    notify_on_approval: bool = True


class AutonomousEvent(BaseModel):
    """Normalized typed event for proactive triggers and event bus."""

    event_id: str
    event_type: str
    source: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    version: str = "1.0"


class EventFilter(BaseModel):
    """Predicate matching filter for event bus subscriptions."""

    event_type_pattern: str
    source_pattern: str | None = None
    payload_predicates: dict[str, Any] = Field(default_factory=dict)

    def matches(self, event: AutonomousEvent) -> bool:
        """Evaluate if an event satisfies filter predicates."""
        if self.event_type_pattern != "*" and self.event_type_pattern != event.event_type:
            if not (
                self.event_type_pattern.endswith("*")
                and event.event_type.startswith(self.event_type_pattern[:-1])
            ):
                return False

        if (
            self.source_pattern
            and self.source_pattern != "*"
            and self.source_pattern != event.source
        ):
            return False

        for k, v in self.payload_predicates.items():
            if event.payload.get(k) != v:
                return False

        return True


class DriftReport(BaseModel):
    """Diagnostic report from GoalDriftDetector."""

    is_drifted: bool
    divergence_score: float
    reason: str
    unauthorized_targets: list[str] = Field(default_factory=list)
    unauthorized_tools: list[str] = Field(default_factory=list)
    objective_divergence: bool = False
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TaskCheckpoint(BaseModel):
    """Cryptographically verifiable snapshot of autonomous task state."""

    checkpoint_id: str
    task_id: str
    version: int
    state: TaskLifecycleState
    budget: ExecutionBudget
    active_plan: list[dict[str, Any]] = Field(default_factory=list)
    completed_steps: list[dict[str, Any]] = Field(default_factory=list)
    execution_evidence: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    checksum: str = ""

    def compute_checksum(self) -> str:
        """Compute SHA-256 integrity hash of checkpoint payload."""
        payload = {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "version": self.version,
            "state": self.state.value,
            "budget": self.budget.model_dump(),
            "active_plan": self.active_plan,
            "completed_steps": self.completed_steps,
        }
        raw_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw_bytes).hexdigest()

    def verify_integrity(self) -> bool:
        """Verify checkpoint payload against its recorded checksum."""
        return self.checksum == self.compute_checksum()


class AutonomousTaskContract(BaseModel):
    """Canonical specification and runtime state of an autonomous task."""

    task_id: str
    user_id: str = "default_user"
    session_id: str = "default_session"
    goal: GoalContract
    schedule_type: ScheduleType = ScheduleType.ONE_SHOT
    schedule_expr: str | None = None
    missed_job_policy: MissedJobPolicy = MissedJobPolicy.EXECUTE_ONCE_NEXT_AVAILABLE
    budget: ExecutionBudget = Field(default_factory=ExecutionBudget)
    drift_policy: DriftPolicy = Field(default_factory=DriftPolicy)
    notification_policy: NotificationPolicy = Field(default_factory=NotificationPolicy)
    allowed_tools: list[str] = Field(default_factory=list)
    prohibited_tools: list[str] = Field(default_factory=list)
    state: TaskLifecycleState = TaskLifecycleState.CREATED
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    owner_device_id: str = "primary_core"
    current_checkpoint_id: str | None = None
    is_cancelled: bool = False
    is_paused: bool = False
    failure_reason: str | None = None


class TaskNotification(BaseModel):
    """User-facing notification emitted by autonomous task workflows."""

    notification_id: str
    task_id: str
    user_id: str
    event_type: str
    title: str
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    data: dict[str, Any] = Field(default_factory=dict)
