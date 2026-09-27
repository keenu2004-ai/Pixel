"""Resource governor and concurrency manager for autonomous tasks."""

import asyncio
import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


class TaskGovernor:
    """Regulates concurrent task execution, active slots, and prevents starvation."""

    def __init__(
        self,
        max_concurrent_tasks: int = 5,
        max_concurrent_inferences: int = 2,
        slice_timeout_seconds: float = 60.0,
    ) -> None:
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_concurrent_inferences = max_concurrent_inferences
        self.slice_timeout_seconds = slice_timeout_seconds

        self._active_tasks: dict[str, datetime] = {}
        self._task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self._inference_semaphore = asyncio.Semaphore(max_concurrent_inferences)
        self._lock = asyncio.Lock()

    async def acquire_task_slot(self, task_id: str) -> bool:
        """Attempt to acquire a concurrent execution slot for a task."""
        async with self._lock:
            if task_id in self._active_tasks:
                return True
            if len(self._active_tasks) >= self.max_concurrent_tasks:
                logger.warning(
                    "Task governor capacity reached (%d/%d)",
                    len(self._active_tasks),
                    self.max_concurrent_tasks,
                )
                return False

            self._active_tasks[task_id] = datetime.now(UTC)
            logger.info(
                "Task slot acquired for '%s' (active: %d)", task_id, len(self._active_tasks)
            )
            return True

    async def release_task_slot(self, task_id: str) -> None:
        """Release task slot upon segment completion or state transition."""
        async with self._lock:
            if task_id in self._active_tasks:
                del self._active_tasks[task_id]
                logger.info(
                    "Task slot released for '%s' (active: %d)", task_id, len(self._active_tasks)
                )

    def get_active_task_count(self) -> int:
        """Return number of currently running task slots."""
        return len(self._active_tasks)

    def is_task_active(self, task_id: str) -> bool:
        """Check if task holds an active execution slot."""
        return task_id in self._active_tasks
