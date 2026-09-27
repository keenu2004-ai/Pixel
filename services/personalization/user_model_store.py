"""PIXEL — User Model Store.

Transactional SQLite-backed and in-memory persistence for formal UserModel aggregates,
ensuring atomic updates, versioning, and Right-to-Forget cascading purges.
"""

import json
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from packages.contracts.personalization import (
    HabitPattern,
    PersonalEntity,
    PersonalGoal,
    UserPreferenceProfile,
    UserRoutine,
)
from packages.contracts.user_model import (
    UserIdentityProfile,
    UserModel,
    UserPrivacyPolicy,
)

logger = logging.getLogger(__name__)


class UserModelStore:
    """Persistent storage engine for formal User Models."""

    def __init__(self, db_path: str = "data/persistence/pixel_user_model.db") -> None:
        self.db_path = Path(db_path)
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        """Closes the underlying SQLite connection."""
        if hasattr(self, "_conn") and self._conn:
            try:
                self._conn.close()
            except Exception:
                pass

    def _init_schema(self) -> None:
        """Initializes tables for user model persistence."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_user_models (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT NOT NULL,
                    preferences_json TEXT NOT NULL,
                    privacy_json TEXT NOT NULL,
                    identity_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_user_goals (
                    goal_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    goal_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_user_routines (
                    routine_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    is_active INTEGER NOT NULL,
                    routine_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_user_habits (
                    habit_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    habit_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_user_entities (
                    entity_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    canonical_name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_goals_user ON pixel_user_goals(user_id)")
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_routines_user ON pixel_user_routines(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_habits_user ON pixel_user_habits(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_entities_user ON pixel_user_entities(user_id)"
            )
            conn.commit()

    async def get_user_model(self, user_id: str = "default_user") -> UserModel:
        """Loads or initializes a user's full model aggregate."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pixel_user_models WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()

            if row:
                identity_data = json.loads(row["identity_json"])
                pref_data = json.loads(row["preferences_json"])
                privacy_data = json.loads(row["privacy_json"])
                metadata = json.loads(row["metadata_json"])
                version = row["version"]
                updated_at_val = datetime.fromisoformat(row["updated_at"])
            else:
                identity_profile = UserIdentityProfile(user_id=user_id)
                pref_profile = UserPreferenceProfile(user_id=user_id)
                privacy_profile = UserPrivacyPolicy()
                identity_json_str = identity_profile.model_dump_json()
                pref_json_str = pref_profile.model_dump_json()
                privacy_json_str = privacy_profile.model_dump_json()
                metadata = {}
                version = 1
                updated_at_val = datetime.now(UTC)
                # Persist baseline row
                now_str = updated_at_val.isoformat()
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO pixel_user_models (user_id, display_name, preferences_json, privacy_json, identity_json, metadata_json, version, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        "User",
                        pref_json_str,
                        privacy_json_str,
                        identity_json_str,
                        json.dumps(metadata),
                        1,
                        now_str,
                    ),
                )
                conn.commit()

                identity_data = json.loads(identity_json_str)
                pref_data = json.loads(pref_json_str)
                privacy_data = json.loads(privacy_json_str)

            # Load child collections
            cursor.execute("SELECT goal_json FROM pixel_user_goals WHERE user_id = ?", (user_id,))
            goals = [PersonalGoal.model_validate_json(r["goal_json"]) for r in cursor.fetchall()]

            cursor.execute(
                "SELECT routine_json FROM pixel_user_routines WHERE user_id = ?", (user_id,)
            )
            routines = [
                UserRoutine.model_validate_json(r["routine_json"]) for r in cursor.fetchall()
            ]

            cursor.execute("SELECT habit_json FROM pixel_user_habits WHERE user_id = ?", (user_id,))
            habits = [HabitPattern.model_validate_json(r["habit_json"]) for r in cursor.fetchall()]

            cursor.execute(
                "SELECT entity_json FROM pixel_user_entities WHERE user_id = ?", (user_id,)
            )
            entities = [
                PersonalEntity.model_validate_json(r["entity_json"]) for r in cursor.fetchall()
            ]

            return UserModel(
                user_id=user_id,
                identity=UserIdentityProfile.model_validate(identity_data),
                preferences=UserPreferenceProfile.model_validate(pref_data),
                privacy_policy=UserPrivacyPolicy.model_validate(privacy_data),
                active_goals=goals,
                routines=routines,
                habits=habits,
                entities=entities,
                custom_metadata=metadata,
                version=version,
                updated_at=updated_at_val,
            )

    async def save_user_model(self, model: UserModel) -> None:
        """Persists the user model aggregate transactionally."""
        now_str = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version FROM pixel_user_models WHERE user_id = ?", (model.user_id,)
            )
            row = cursor.fetchone()
            new_version = (row["version"] + 1) if row else model.version
            model.version = new_version
            cursor.execute(
                """
                INSERT INTO pixel_user_models (user_id, display_name, preferences_json, privacy_json, identity_json, metadata_json, version, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    display_name=excluded.display_name,
                    preferences_json=excluded.preferences_json,
                    privacy_json=excluded.privacy_json,
                    identity_json=excluded.identity_json,
                    metadata_json=excluded.metadata_json,
                    version=excluded.version,
                    updated_at=excluded.updated_at
                """,
                (
                    model.user_id,
                    model.identity.display_name,
                    model.preferences.model_dump_json(),
                    model.privacy_policy.model_dump_json(),
                    model.identity.model_dump_json(),
                    json.dumps(model.custom_metadata),
                    new_version,
                    now_str,
                ),
            )
            conn.commit()

    async def save_goal(self, goal: PersonalGoal) -> None:
        """Saves or updates a personal goal."""
        now_str = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_user_goals (goal_id, user_id, title, status, priority, goal_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(goal_id) DO UPDATE SET
                    title=excluded.title,
                    status=excluded.status,
                    priority=excluded.priority,
                    goal_json=excluded.goal_json,
                    updated_at=excluded.updated_at
                """,
                (
                    goal.goal_id,
                    goal.user_id,
                    goal.title,
                    str(goal.status),
                    goal.priority,
                    goal.model_dump_json(),
                    now_str,
                ),
            )
            conn.commit()

    async def save_routine(self, routine: UserRoutine) -> None:
        """Saves or updates a user routine."""
        now_str = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_user_routines (routine_id, user_id, name, is_active, routine_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(routine_id) DO UPDATE SET
                    name=excluded.name,
                    is_active=excluded.is_active,
                    routine_json=excluded.routine_json,
                    updated_at=excluded.updated_at
                """,
                (
                    routine.routine_id,
                    routine.user_id,
                    routine.name,
                    1 if routine.is_active else 0,
                    routine.model_dump_json(),
                    now_str,
                ),
            )
            conn.commit()

    async def save_habit(self, habit: HabitPattern) -> None:
        """Saves or updates a habit pattern."""
        now_str = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_user_habits (habit_id, user_id, name, status, habit_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(habit_id) DO UPDATE SET
                    name=excluded.name,
                    status=excluded.status,
                    habit_json=excluded.habit_json,
                    updated_at=excluded.updated_at
                """,
                (
                    habit.habit_id,
                    habit.user_id,
                    habit.name,
                    str(habit.status),
                    habit.model_dump_json(),
                    now_str,
                ),
            )
            conn.commit()

    async def save_entity(self, entity: PersonalEntity) -> None:
        """Saves or updates a personal entity."""
        now_str = datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_user_entities (entity_id, user_id, canonical_name, entity_type, entity_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    canonical_name=excluded.canonical_name,
                    entity_type=excluded.entity_type,
                    entity_json=excluded.entity_json,
                    updated_at=excluded.updated_at
                """,
                (
                    entity.entity_id,
                    entity.user_id,
                    entity.canonical_name,
                    str(entity.entity_type),
                    entity.model_dump_json(),
                    now_str,
                ),
            )
            conn.commit()

    async def purge_user_data(self, user_id: str, keyword: str | None = None) -> int:
        """Right-to-Forget cascade purge across all user model tables."""
        purged = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if keyword:
                pattern = f"%{keyword.lower().strip()}%"
                cursor.execute(
                    "DELETE FROM pixel_user_goals WHERE user_id = ? AND LOWER(title) LIKE ?",
                    (user_id, pattern),
                )
                purged += cursor.rowcount
                cursor.execute(
                    "DELETE FROM pixel_user_routines WHERE user_id = ? AND LOWER(name) LIKE ?",
                    (user_id, pattern),
                )
                purged += cursor.rowcount
                cursor.execute(
                    "DELETE FROM pixel_user_habits WHERE user_id = ? AND LOWER(name) LIKE ?",
                    (user_id, pattern),
                )
                purged += cursor.rowcount
                cursor.execute(
                    "DELETE FROM pixel_user_entities WHERE user_id = ? AND (LOWER(canonical_name) LIKE ? OR LOWER(entity_json) LIKE ?)",
                    (user_id, pattern, pattern),
                )
                purged += cursor.rowcount
            else:
                cursor.execute("DELETE FROM pixel_user_goals WHERE user_id = ?", (user_id,))
                purged += cursor.rowcount
                cursor.execute("DELETE FROM pixel_user_routines WHERE user_id = ?", (user_id,))
                purged += cursor.rowcount
                cursor.execute("DELETE FROM pixel_user_habits WHERE user_id = ?", (user_id,))
                purged += cursor.rowcount
                cursor.execute("DELETE FROM pixel_user_entities WHERE user_id = ?", (user_id,))
                purged += cursor.rowcount
                cursor.execute("DELETE FROM pixel_user_models WHERE user_id = ?", (user_id,))
                purged += cursor.rowcount
            conn.commit()
        return purged
