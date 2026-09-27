"""Notification manager and dispatcher for autonomous task events."""

import logging
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    NotificationPolicy,
    TaskNotification,
)

logger = logging.getLogger(__name__)


class TaskNotificationManager:
    """Manages user-facing notification dispatch and deduplication for autonomous tasks."""

    def __init__(self) -> None:
        self._handlers: list[Callable[[TaskNotification], None]] = []
        self._emitted_notifications: list[TaskNotification] = []

    def register_handler(self, handler: Callable[[TaskNotification], None]) -> None:
        """Register a notification consumer callback."""
        self._handlers.append(handler)

    def notify(
        self,
        task: AutonomousTaskContract,
        event_type: str,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> TaskNotification | None:
        """Evaluate policy and emit notification if permitted."""
        policy: NotificationPolicy = task.notification_policy

        should_send = False
        if event_type == "START" and policy.notify_on_start:
            should_send = True
        elif event_type == "COMPLETE" and policy.notify_on_complete:
            should_send = True
        elif event_type == "FAILURE" and policy.notify_on_failure:
            should_send = True
        elif event_type == "DRIFT" and policy.notify_on_drift:
            should_send = True
        elif event_type == "APPROVAL_REQUIRED" and policy.notify_on_approval:
            should_send = True

        if not should_send:
            return None

        notif = TaskNotification(
            notification_id=f"notif_{uuid.uuid4().hex[:12]}",
            task_id=task.task_id,
            user_id=task.user_id,
            event_type=event_type,
            title=title,
            message=message,
            timestamp=datetime.now(UTC),
            data=data or {},
        )

        self._emitted_notifications.append(notif)
        logger.info(
            "Emitted notification '%s' for task '%s': %s",
            notif.notification_id,
            task.task_id,
            title,
        )

        for handler in self._handlers:
            try:
                handler(notif)
            except Exception:
                logger.exception("Error in notification handler")

        return notif

    def get_notifications_for_task(self, task_id: str) -> list[TaskNotification]:
        """Return history of emitted notifications for a task."""
        return [n for n in self._emitted_notifications if n.task_id == task_id]
