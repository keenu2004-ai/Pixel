"""Persistent budget accounting and enforcement for autonomous tasks."""

import logging
import sqlite3
from datetime import UTC, datetime

from packages.contracts.autonomous import ExecutionBudget

logger = logging.getLogger(__name__)


class BudgetManager:
    """Manages and persists execution resource consumption across restarts."""

    def __init__(self, db_path: str = ":memory:") -> None:
        self.db_path = db_path
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
                CREATE TABLE IF NOT EXISTS task_budgets (
                    task_id TEXT PRIMARY KEY,
                    max_steps INTEGER NOT NULL,
                    max_tool_calls INTEGER NOT NULL,
                    max_duration_seconds REAL NOT NULL,
                    max_retries INTEGER NOT NULL,
                    max_tokens INTEGER NOT NULL,
                    consumed_steps INTEGER NOT NULL,
                    consumed_tool_calls INTEGER NOT NULL,
                    consumed_duration_seconds REAL NOT NULL,
                    consumed_retries INTEGER NOT NULL,
                    consumed_tokens INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def initialize_task_budget(self, task_id: str, budget: ExecutionBudget) -> None:
        """Register initial or existing budget limits for a task."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO task_budgets (
                    task_id, max_steps, max_tool_calls, max_duration_seconds,
                    max_retries, max_tokens, consumed_steps, consumed_tool_calls,
                    consumed_duration_seconds, consumed_retries, consumed_tokens,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    budget.max_steps,
                    budget.max_tool_calls,
                    budget.max_duration_seconds,
                    budget.max_retries,
                    budget.max_tokens,
                    budget.consumed_steps,
                    budget.consumed_tool_calls,
                    budget.consumed_duration_seconds,
                    budget.consumed_retries,
                    budget.consumed_tokens,
                    datetime.now(UTC).isoformat(),
                ),
            )
            conn.commit()

    def record_step(
        self,
        task_id: str,
        steps: int = 1,
        tool_calls: int = 0,
        duration_seconds: float = 0.0,
        tokens: int = 0,
        retries: int = 0,
    ) -> tuple[bool, ExecutionBudget, str | None]:
        """Atomically increment consumption metrics and verify bounds."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM task_budgets WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No budget registered for task '{task_id}'")

            new_steps = row["consumed_steps"] + steps
            new_tools = row["consumed_tool_calls"] + tool_calls
            new_dur = row["consumed_duration_seconds"] + duration_seconds
            new_tokens = row["consumed_tokens"] + tokens
            new_retries = row["consumed_retries"] + retries

            conn.execute(
                """
                UPDATE task_budgets
                SET consumed_steps = ?,
                    consumed_tool_calls = ?,
                    consumed_duration_seconds = ?,
                    consumed_tokens = ?,
                    consumed_retries = ?,
                    updated_at = ?
                WHERE task_id = ?
                """,
                (
                    new_steps,
                    new_tools,
                    new_dur,
                    new_tokens,
                    new_retries,
                    datetime.now(UTC).isoformat(),
                    task_id,
                ),
            )
            conn.commit()

            current_budget = ExecutionBudget(
                max_steps=row["max_steps"],
                max_tool_calls=row["max_tool_calls"],
                max_duration_seconds=row["max_duration_seconds"],
                max_retries=row["max_retries"],
                max_tokens=row["max_tokens"],
                consumed_steps=new_steps,
                consumed_tool_calls=new_tools,
                consumed_duration_seconds=new_dur,
                consumed_tokens=new_tokens,
                consumed_retries=new_retries,
            )

            is_breached, reason = current_budget.is_exceeded()
            if is_breached:
                logger.warning("Task '%s' budget breach: %s", task_id, reason)

            return (not is_breached), current_budget, reason

    def get_budget(self, task_id: str) -> ExecutionBudget | None:
        """Fetch current budget consumption state for a task."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM task_budgets WHERE task_id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None

            return ExecutionBudget(
                max_steps=row["max_steps"],
                max_tool_calls=row["max_tool_calls"],
                max_duration_seconds=row["max_duration_seconds"],
                max_retries=row["max_retries"],
                max_tokens=row["max_tokens"],
                consumed_steps=row["consumed_steps"],
                consumed_tool_calls=row["consumed_tool_calls"],
                consumed_duration_seconds=row["consumed_duration_seconds"],
                consumed_retries=row["consumed_retries"],
                consumed_tokens=row["consumed_tokens"],
            )
