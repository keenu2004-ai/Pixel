"""SQLite Memory Storage Engine for PIXEL.

Provides transactional persistence for Facts (Semantic Memory) and Episodes (Episodic Memory)
with vector similarity search, conflict resolution, and Right to Forget deletion.
"""

import json
import logging
import math
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from packages.contracts.memory import EpisodeRecord, FactRecord
from packages.core.interfaces.embeddings import BaseEmbeddingProvider
from packages.core.interfaces.memory import BaseMemoryStore
from services.rag.embeddings.hash_embedding import DeterministicHashEmbeddingProvider

logger = logging.getLogger(__name__)


def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Computes cosine similarity between two normalized vectors."""
    if not vec1 or not vec2 or len(vec1) != len(vec2):
        return 0.0
    dot = sum(a * b for a, b in zip(vec1, vec2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 > 1e-9 and norm2 > 1e-9:
        return dot / (norm1 * norm2)
    return 0.0


class SQLiteMemoryStore(BaseMemoryStore):
    """Production-grade SQLite-backed memory store."""

    def __init__(
        self,
        db_path: str = "data/persistence/pixel_memory.db",
        embedding_provider: BaseEmbeddingProvider | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.embedding_provider = embedding_provider or DeterministicHashEmbeddingProvider()
        self._init_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        """Initializes database tables and indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 1. Semantic Facts Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_facts (
                    fact_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_json TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    provenance TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    superseded_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_facts_user_key ON pixel_facts(user_id, key, is_active)"
            )

            # 2. Episodic Memory Table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pixel_episodes (
                    episode_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    interaction_type TEXT NOT NULL,
                    embedding_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_episodes_user ON pixel_episodes(user_id)"
            )
            conn.commit()

    async def get_fact(self, key: str, user_id: str) -> Any | None:
        """Retrieves active fact value by key."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT value_json FROM pixel_facts WHERE user_id = ? AND key = ? AND is_active = 1 ORDER BY updated_at DESC LIMIT 1",
                (user_id, key),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["value_json"])
            return None

    async def set_fact(
        self,
        key: str,
        value: Any,
        user_id: str,
        category: str = "general",
        provenance: str = "user_explicit",
        confidence: float = 1.0,
    ) -> FactRecord:
        """Stores a semantic fact, superseding any existing active fact with the same key."""
        new_fact_id = uuid4().hex
        now_str = datetime.now(UTC).isoformat()
        val_json = json.dumps(value)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Deactivate previous active facts for this key
            cursor.execute(
                "UPDATE pixel_facts SET is_active = 0, superseded_by = ?, updated_at = ? WHERE user_id = ? AND key = ? AND is_active = 1",
                (new_fact_id, now_str, user_id, key),
            )
            # Insert new fact
            cursor.execute(
                """
                INSERT INTO pixel_facts (fact_id, user_id, category, key, value_json, confidence, provenance, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    new_fact_id,
                    user_id,
                    category,
                    key,
                    val_json,
                    confidence,
                    provenance,
                    now_str,
                    now_str,
                ),
            )
            conn.commit()

        return FactRecord(
            fact_id=new_fact_id,
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            provenance=provenance,
            is_active=True,
        )

    async def list_facts(self, user_id: str, category: str | None = None) -> list[FactRecord]:
        """Lists all active facts for a user."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if category:
                cursor.execute(
                    "SELECT * FROM pixel_facts WHERE user_id = ? AND category = ? AND is_active = 1 ORDER BY updated_at DESC",
                    (user_id, category),
                )
            else:
                cursor.execute(
                    "SELECT * FROM pixel_facts WHERE user_id = ? AND is_active = 1 ORDER BY updated_at DESC",
                    (user_id,),
                )
            rows = cursor.fetchall()
            return [
                FactRecord(
                    fact_id=r["fact_id"],
                    user_id=r["user_id"],
                    category=r["category"],
                    key=r["key"],
                    value=json.loads(r["value_json"]),
                    confidence=r["confidence"],
                    provenance=r["provenance"],
                    is_active=bool(r["is_active"]),
                    superseded_by=r["superseded_by"],
                    created_at=datetime.fromisoformat(r["created_at"]),
                    updated_at=datetime.fromisoformat(r["updated_at"]),
                )
                for r in rows
            ]

    async def delete_fact(self, key: str, user_id: str) -> bool:
        """Physical purge / deletion of specific fact (Right to Forget)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM pixel_facts WHERE user_id = ? AND key = ?", (user_id, key))
            conn.commit()
            return cursor.rowcount > 0

    async def forget_topic(self, keyword: str, user_id: str) -> int:
        """Cryptographically purges all facts and episodes matching a keyword (Right to Forget)."""
        pattern = f"%{keyword.lower().strip()}%"
        deleted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Delete matching facts
            cursor.execute(
                "DELETE FROM pixel_facts WHERE user_id = ? AND (LOWER(key) LIKE ? OR LOWER(value_json) LIKE ?)",
                (user_id, pattern, pattern),
            )
            deleted_count += cursor.rowcount

            # Delete matching episodes
            cursor.execute(
                "DELETE FROM pixel_episodes WHERE user_id = ? AND LOWER(summary) LIKE ?",
                (user_id, pattern),
            )
            deleted_count += cursor.rowcount
            conn.commit()

        logger.info(
            "Right to Forget: Purged %d records for keyword '%s' (user: %s)",
            deleted_count,
            keyword,
            user_id,
        )
        return deleted_count

    async def record_episode(
        self,
        summary: str,
        session_id: str,
        user_id: str,
        interaction_type: str = "conversation",
        metadata: dict[str, Any] | None = None,
    ) -> EpisodeRecord:
        """Embeds and persists an interaction summary in episodic memory."""
        ep_id = uuid4().hex
        now_str = datetime.now(UTC).isoformat()
        embedding = await self.embedding_provider.embed_text(summary)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO pixel_episodes (episode_id, user_id, session_id, summary, interaction_type, embedding_json, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ep_id,
                    user_id,
                    session_id,
                    summary,
                    interaction_type,
                    json.dumps(embedding),
                    json.dumps(metadata or {}),
                    now_str,
                ),
            )
            conn.commit()

        return EpisodeRecord(
            episode_id=ep_id,
            user_id=user_id,
            session_id=session_id,
            summary=summary,
            interaction_type=interaction_type,
            embedding=embedding,
            metadata=metadata or {},
        )

    async def search_episodic(
        self, query: str, user_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        """Semantic vector search over user's episodic history."""
        query_vec = await self.embedding_provider.embed_text(query)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pixel_episodes WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            emb = json.loads(r["embedding_json"])
            sim = _cosine_similarity(query_vec, emb)
            results.append(
                {
                    "episode_id": r["episode_id"],
                    "summary": r["summary"],
                    "session_id": r["session_id"],
                    "similarity": sim,
                    "metadata": json.loads(r["metadata_json"]),
                    "created_at": r["created_at"],
                }
            )

        # Sort descending by similarity
        results.sort(key=lambda x: float(x["similarity"]), reverse=True)
        return results[:limit]
