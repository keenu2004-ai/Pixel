"""Abstract base interfaces for Phase 9 Proactive & Autonomous Workflows."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

from packages.contracts.autonomous import (
    AutonomousEvent,
    AutonomousTaskContract,
    DriftReport,
    EventFilter,
    GoalContract,
    TaskLifecycleState,
)


class BaseEventBus(ABC):
    """Abstract interface for typed, deduplicated event bus."""

    @abstractmethod
    async def publish(self, event: AutonomousEvent) -> int:
        """Publish an event to all matching subscribers. Returns count of dispatched handlers."""
        raise NotImplementedError

    @abstractmethod
    def subscribe(
        self,
        subscriber_id: str,
        filter_pred: EventFilter,
        callback: Callable[[AutonomousEvent], Awaitable[None]],
    ) -> None:
        """Register a subscriber with a predicate filter and async callback."""
        raise NotImplementedError

    @abstractmethod
    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscriber by ID."""
        raise NotImplementedError

    @abstractmethod
    def is_duplicate(self, event: AutonomousEvent) -> bool:
        """Check if an event was already processed based on event_id or idempotency_key."""
        raise NotImplementedError


class BaseScheduler(ABC):
    """Abstract interface for persistent task scheduling."""

    @abstractmethod
    def schedule_task(self, task: AutonomousTaskContract) -> bool:
        """Persist and schedule a task."""
        raise NotImplementedError

    @abstractmethod
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a scheduled task."""
        raise NotImplementedError

    @abstractmethod
    def pause_task(self, task_id: str) -> bool:
        """Pause a running or scheduled task."""
        raise NotImplementedError

    @abstractmethod
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        raise NotImplementedError

    @abstractmethod
    def get_task(self, task_id: str) -> AutonomousTaskContract | None:
        """Retrieve task specification and current state."""
        raise NotImplementedError

    @abstractmethod
    def list_due_tasks(self, now: datetime | None = None) -> list[AutonomousTaskContract]:
        """List all tasks due for execution at the given reference time."""
        raise NotImplementedError

    @abstractmethod
    def update_task_state(self, task_id: str, state: TaskLifecycleState) -> bool:
        """Update lifecycle state of a task."""
        raise NotImplementedError


class BaseDriftDetector(ABC):
    """Abstract interface for autonomous goal drift detection."""

    @abstractmethod
    def evaluate_drift(
        self,
        goal: GoalContract,
        active_plan: list[dict[str, Any]],
        proposed_tools: list[str],
        proposed_targets: list[str],
        current_objective: str | None = None,
    ) -> DriftReport:
        """Evaluate whether the agent's proposed plan, tools, and targets drift from the immutable GoalContract."""
        raise NotImplementedError


class BaseAutonomousEngine(ABC):
    """Abstract interface for executing bounded autonomous workflows."""

    @abstractmethod
    async def submit_task(self, task: AutonomousTaskContract) -> str:
        """Register and authorize a new autonomous task."""
        raise NotImplementedError

    @abstractmethod
    async def execute_task_segment(self, task_id: str, max_steps: int = 5) -> TaskLifecycleState:
        """Execute a single bounded slice of an autonomous task."""
        raise NotImplementedError

    @abstractmethod
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an autonomous task."""
        raise NotImplementedError

    @abstractmethod
    async def pause_task(self, task_id: str) -> bool:
        """Pause an autonomous task."""
        raise NotImplementedError

    @abstractmethod
    async def resume_task(self, task_id: str) -> bool:
        """Resume an autonomous task after pause."""
        raise NotImplementedError
