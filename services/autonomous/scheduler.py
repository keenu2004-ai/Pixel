"""Persistent task scheduler for autonomous workflows with SQLite storage and missed-job recovery."""

import json
import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    MissedJobPolicy,
    ScheduleType,
    TaskLifecycleState,
)
from packages.core.interfaces.autonomous import BaseScheduler

logger = logging.getLogger(__name__)


class AutonomousScheduler(BaseScheduler):
    """Persistent scheduler storing task metadata, recurrence, and next run times in SQLite."""

    def __init__(
        self,
        db_path: str = ":memory:",
        time_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.db_path = db_path
        self._time_fn = time_fn or (lambda: datetime.now(UTC))
        self._memory_conn: sqlite3.Connection | None = None
        if self.db_path == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:")
            self._memory_conn.row_factory = sqlite3.Row
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._memory_conn is not None:
            return self._memory_conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS autonomous_tasks (
                    task_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    goal_json TEXT NOT NULL,
                    schedule_type TEXT NOT NULL,
                    schedule_expr TEXT,
                    missed_job_policy TEXT NOT NULL,
                    budget_json TEXT NOT NULL,
                    drift_policy_json TEXT NOT NULL,
                    notification_policy_json TEXT NOT NULL,
                    allowed_tools_json TEXT NOT NULL,
                    prohibited_tools_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_run_at TEXT,
                    next_run_at TEXT,
                    owner_device_id TEXT NOT NULL,
                    current_checkpoint_id TEXT,
                    is_cancelled INTEGER NOT NULL,
                    is_paused INTEGER NOT NULL,
                    failure_reason TEXT
                )
                """
            )
            conn.commit()

    def _calculate_next_run(
        self, task: AutonomousTaskContract, reference_time: datetime
    ) -> datetime | None:
        """Calculate next scheduled execution timestamp."""
        if task.schedule_type == ScheduleType.ONE_SHOT:
            if task.schedule_expr:
                try:
                    return datetime.fromisoformat(task.schedule_expr)
                except ValueError:
                    return reference_time
            return reference_time

        elif task.schedule_type == ScheduleType.INTERVAL:
            seconds = 60.0
            if task.schedule_expr:
                expr = task.schedule_expr.strip()
                if expr.startswith("interval:"):
                    raw = expr.replace("interval:", "").strip()
                    if raw.endswith("s"):
                        seconds = float(raw[:-1])
                    elif raw.endswith("m"):
                        seconds = float(raw[:-1]) * 60.0
                    elif raw.endswith("h"):
                        seconds = float(raw[:-1]) * 3600.0
                    else:
                        seconds = float(raw)
            return reference_time + timedelta(seconds=seconds)

        elif task.schedule_type == ScheduleType.EVENT_DRIVEN:
            return None

        return reference_time

    def schedule_task(self, task: AutonomousTaskContract) -> bool:
        """Persist task and set its initial scheduled time."""
        now = self._time_fn()
        if task.next_run_at is None and task.schedule_type != ScheduleType.EVENT_DRIVEN:
            task.next_run_at = self._calculate_next_run(task, now)

        if task.state == TaskLifecycleState.CREATED:
            task.state = TaskLifecycleState.SCHEDULED

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO autonomous_tasks (
                    task_id, user_id, session_id, goal_json, schedule_type, schedule_expr,
                    missed_job_policy, budget_json, drift_policy_json, notification_policy_json,
                    allowed_tools_json, prohibited_tools_json, state, created_at,
                    last_run_at, next_run_at, owner_device_id, current_checkpoint_id,
                    is_cancelled, is_paused, failure_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.user_id,
                    task.session_id,
                    task.goal.model_dump_json(),
                    task.schedule_type.value,
                    task.schedule_expr,
                    task.missed_job_policy.value,
                    task.budget.model_dump_json(),
                    task.drift_policy.model_dump_json(),
                    task.notification_policy.model_dump_json(),
                    json.dumps(task.allowed_tools),
                    json.dumps(task.prohibited_tools),
                    task.state.value,
                    task.created_at.isoformat(),
                    task.last_run_at.isoformat() if task.last_run_at else None,
                    task.next_run_at.isoformat() if task.next_run_at else None,
                    task.owner_device_id,
                    task.current_checkpoint_id,
                    1 if task.is_cancelled else 0,
                    1 if task.is_paused else 0,
                    task.failure_reason,
                ),
            )
            conn.commit()

        logger.info(
            "Task '%s' scheduled (next_run: %s, state: %s)",
            task.task_id,
            task.next_run_at,
            task.state,
        )
        return True

    def get_task(self, task_id: str) -> AutonomousTaskContract | None:
        """Retrieve task specification by task_id."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM autonomous_tasks WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def list_due_tasks(self, now: datetime | None = None) -> list[AutonomousTaskContract]:
        """List tasks ready to execute at the given reference time."""
        current_time = now or self._time_fn()
        iso_now = current_time.isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM autonomous_tasks
                WHERE is_cancelled = 0
                  AND is_paused = 0
                  AND state IN ('SCHEDULED', 'RUNNING')
                  AND next_run_at IS NOT NULL
                  AND next_run_at <= ?
                ORDER BY next_run_at ASC
                """,
                (iso_now,),
            )
            rows = cursor.fetchall()
            due_tasks: list[AutonomousTaskContract] = []
            for row in rows:
                task = self._row_to_task(row)
                self._handle_missed_job_policy(task, current_time)
                due_tasks.append(task)
            return due_tasks

    def _handle_missed_job_policy(
        self, task: AutonomousTaskContract, current_time: datetime
    ) -> None:
        """Apply missed-job policy if task was severely delayed (> 60s past scheduled time)."""
        if task.next_run_at and (current_time - task.next_run_at).total_seconds() > 60.0:
            if task.missed_job_policy == MissedJobPolicy.SKIP:
                logger.warning("Missed job policy SKIP applied to task '%s'", task.task_id)
                task.next_run_at = self._calculate_next_run(task, current_time)
                self.schedule_task(task)
            elif task.missed_job_policy == MissedJobPolicy.REQUIRE_APPROVAL:
                logger.warning(
                    "Missed job policy REQUIRE_APPROVAL applied to task '%s'", task.task_id
                )
                task.state = TaskLifecycleState.AWAITING_APPROVAL
                self.schedule_task(task)

    def cancel_task(self, task_id: str) -> bool:
        """Mark task as permanently CANCELLED and prevent future execution."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE autonomous_tasks
                SET is_cancelled = 1, state = 'CANCELLED'
                WHERE task_id = ?
                """,
                (task_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def pause_task(self, task_id: str) -> bool:
        """Mark task as PAUSED."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE autonomous_tasks
                SET is_paused = 1, state = 'PAUSED'
                WHERE task_id = ? AND is_cancelled = 0
                """,
                (task_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def resume_task(self, task_id: str) -> bool:
        """Resume a PAUSED task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE autonomous_tasks
                SET is_paused = 0, state = 'SCHEDULED'
                WHERE task_id = ? AND is_cancelled = 0
                """,
                (task_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_task_state(self, task_id: str, state: TaskLifecycleState) -> bool:
        """Update lifecycle state of a task."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                UPDATE autonomous_tasks
                SET state = ?
                WHERE task_id = ?
                """,
                (state.value, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def _row_to_task(self, row: sqlite3.Row) -> AutonomousTaskContract:
        """Deserialize database row to AutonomousTaskContract."""
        from packages.contracts.autonomous import (
            DriftPolicy,
            ExecutionBudget,
            GoalContract,
            NotificationPolicy,
        )

        return AutonomousTaskContract(
            task_id=row["task_id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            goal=GoalContract.model_validate_json(row["goal_json"]),
            schedule_type=ScheduleType(row["schedule_type"]),
            schedule_expr=row["schedule_expr"],
            missed_job_policy=MissedJobPolicy(row["missed_job_policy"]),
            budget=ExecutionBudget.model_validate_json(row["budget_json"]),
            drift_policy=DriftPolicy.model_validate_json(row["drift_policy_json"]),
            notification_policy=NotificationPolicy.model_validate_json(
                row["notification_policy_json"]
            ),
            allowed_tools=json.loads(row["allowed_tools_json"]),
            prohibited_tools=json.loads(row["prohibited_tools_json"]),
            state=TaskLifecycleState(row["state"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            last_run_at=datetime.fromisoformat(row["last_run_at"]) if row["last_run_at"] else None,
            next_run_at=datetime.fromisoformat(row["next_run_at"]) if row["next_run_at"] else None,
            owner_device_id=row["owner_device_id"],
            current_checkpoint_id=row["current_checkpoint_id"],
            is_cancelled=bool(row["is_cancelled"]),
            is_paused=bool(row["is_paused"]),
            failure_reason=row["failure_reason"],
        )
