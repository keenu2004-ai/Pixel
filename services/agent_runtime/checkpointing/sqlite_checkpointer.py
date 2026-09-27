"""SQLite Checkpointer for Agent State Persistence and Recovery."""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from packages.contracts.agent import AgentCheckpoint, AgentExecutionStatus, AgentState
from packages.core.interfaces.checkpointer import BaseCheckpointer

logger = logging.getLogger(__name__)


class SQLiteCheckpointer(BaseCheckpointer):
    """Production SQLite-backed checkpointer with transactional guarantees and recovery."""

    CURRENT_VERSION = 1

    def __init__(self, db_path: str = "data/persistence/pixel_checkpoints.db") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_agent_checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_task ON pixel_agent_checkpoints(task_id, created_at)")
            conn.commit()

    async def save_checkpoint(self, state: AgentState, version: int = CURRENT_VERSION) -> str:
        """Persists agent state checkpoint into SQLite."""
        checkpoint_id = uuid4().hex
        state_json = state.model_dump_json()
        now_str = state.updated_at.isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_agent_checkpoints (checkpoint_id, task_id, session_id, version, status, state_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint_id,
                    state.task_id,
                    state.session_id,
                    version,
                    state.status.value,
                    state_json,
                    now_str,
                ),
            )
            conn.commit()

        logger.debug("Saved agent checkpoint %s for task %s (status: %s)", checkpoint_id, state.task_id, state.status)
        return checkpoint_id

    async def get_latest_checkpoint(self, task_id: str) -> AgentState | None:
        """Retrieves and deserializes the latest state for a given task ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pixel_agent_checkpoints WHERE task_id = ? ORDER BY created_at DESC LIMIT 1",
                (task_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

        # Deserialization and version handling
        try:
            raw_json = row["state_json"]
            version = row["version"]
            if version > self.CURRENT_VERSION:
                logger.warning("Checkpoint version %d is newer than supported %d for task %s", version, self.CURRENT_VERSION, task_id)

            data = json.loads(raw_json)
            return AgentState.model_validate(data)
        except Exception as err:
            logger.error("Corrupted checkpoint encountered for task %s: %s", task_id, err)
            return None

    async def list_checkpoints(self, task_id: str) -> list[AgentCheckpoint]:
        """Lists all persisted checkpoint records for a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM pixel_agent_checkpoints WHERE task_id = ? ORDER BY created_at ASC",
                (task_id,),
            )
            rows = cursor.fetchall()

        return [
            AgentCheckpoint(
                checkpoint_id=r["checkpoint_id"],
                task_id=r["task_id"],
                session_id=r["session_id"],
                version=r["version"],
                status=AgentExecutionStatus(r["status"]),
                state_json=r["state_json"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    async def delete_checkpoints(self, task_id: str) -> bool:
        """Deletes all checkpoints for a task."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pixel_agent_checkpoints WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0
