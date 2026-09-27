"""Unified Hierarchical Memory Manager for PIXEL.

Coordinates Tier 1 (Working Memory), Tier 2 (Episodic Memory), Tier 3 (Semantic Memory),
and background extraction tasks with bounded queue safety.
"""

import asyncio
import logging
from collections import deque
from typing import Any

from packages.core.interfaces.embeddings import BaseEmbeddingProvider
from services.memory.extraction_agent import MemoryExtractor
from services.memory.stores.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger(__name__)


class WorkingMemory:
    """Tier 1 ephemeral short-term session buffer."""

    def __init__(self, max_turns: int = 20) -> None:
        self.max_turns = max_turns
        self._history: deque[dict[str, str]] = deque(maxlen=max_turns)

    def add_turn(self, user_text: str, assistant_text: str) -> None:
        self._history.append({"user": user_text, "assistant": assistant_text})

    def get_recent_context(self, turns: int = 5) -> list[dict[str, str]]:
        return list(self._history)[-turns:]

    def clear(self) -> None:
        self._history.clear()


class MemoryManager:
    """Unified coordinator for PIXEL memory tiers."""

    def __init__(
        self,
        db_path: str = "data/persistence/pixel_memory.db",
        store: SQLiteMemoryStore | None = None,
        embedding_provider: BaseEmbeddingProvider | None = None,
        working_memory_capacity: int = 20,
    ) -> None:
        self.store = store or SQLiteMemoryStore(db_path=db_path, embedding_provider=embedding_provider)
        self.extractor = MemoryExtractor(memory_store=self.store)
        self.working_memory_capacity = working_memory_capacity
        self.working_memories: dict[str, WorkingMemory] = {}
        self._bg_tasks: set[asyncio.Task[Any]] = set()

    def get_working_memory(self, session_id: str) -> list[dict[str, str]]:
        """Retrieves list of recent interaction turns for a session."""
        if session_id not in self.working_memories:
            self.working_memories[session_id] = WorkingMemory(max_turns=self.working_memory_capacity)
        return self.working_memories[session_id].get_recent_context(turns=self.working_memory_capacity)

    def get_working_memory_buffer(self, session_id: str) -> WorkingMemory:
        """Retrieves the underlying WorkingMemory buffer object."""
        if session_id not in self.working_memories:
            self.working_memories[session_id] = WorkingMemory(max_turns=self.working_memory_capacity)
        return self.working_memories[session_id]

    async def record_interaction(
        self,
        user_query: str | None = None,
        assistant_response: str | None = None,
        session_id: str = "default_session",
        user_id: str = "default_user",
        user_input: str | None = None,
        agent_response: str | None = None,
    ) -> None:
        """Updates Tier 1 working memory immediately and queues Tier 2/3 extraction in the background."""
        u_text = user_query or user_input or ""
        a_text = assistant_response or agent_response or ""

        # 1. Immediate Tier 1 update
        wm = self.get_working_memory_buffer(session_id)
        wm.add_turn(u_text, a_text)

        # 2. Asynchronous background extraction (non-blocking)
        task = asyncio.create_task(
            self._safe_extract(u_text, a_text, session_id, user_id)
        )
        self._bg_tasks.add(task)
        task.add_done_callback(self._bg_tasks.discard)

    async def _safe_extract(
        self,
        user_query: str,
        assistant_response: str,
        session_id: str,
        user_id: str,
    ) -> None:
        try:
            await self.extractor.extract_and_persist(
                user_query=user_query,
                assistant_response=assistant_response,
                session_id=session_id,
                user_id=user_id,
            )
        except Exception as err:
            logger.error("Background memory extraction error: %s", err)

    async def query_relevant_memory(
        self,
        query: str,
        user_id: str = "default_user",
        top_k_episodes: int = 3,
    ) -> dict[str, Any]:
        """Gathers relevant semantic facts and episodic history for context injection."""
        facts = await self.store.list_facts(user_id=user_id)
        episodes = await self.store.search_episodic(query=query, user_id=user_id, limit=top_k_episodes)
        return {
            "facts": [f.model_dump() for f in facts],
            "episodes": episodes,
        }

    async def query_context(
        self,
        query: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
        top_k_episodes: int = 3,
    ) -> dict[str, Any]:
        """Unified context assembly including working memory, active facts, and episodic context."""
        mem = await self.query_relevant_memory(query=query, user_id=user_id, top_k_episodes=top_k_episodes)
        working_ctx = self.get_working_memory(session_id=session_id)
        mem["working_context"] = working_ctx
        return mem

    async def forget(self, keyword: str, user_id: str = "default_user") -> int:
        """Executes Right to Forget deletion across facts and interaction history."""
        return await self.store.forget_topic(keyword=keyword, user_id=user_id)

    async def forget_topic(self, keyword: str, user_id: str = "default_user") -> int:
        """Right to Forget alias."""
        return await self.forget(keyword=keyword, user_id=user_id)
