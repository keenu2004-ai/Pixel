"""Abstract Interface for Layered Memory Stores."""

from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.memory import FactRecord


class BaseMemoryStore(ABC):
    """Abstract base store for L9 Episodic and Semantic Memory."""

    @abstractmethod
    async def get_fact(self, key: str, user_id: str) -> Any | None:
        """Retrieves a verified semantic fact for a user."""
        pass

    @abstractmethod
    async def set_fact(
        self,
        key: str,
        value: Any,
        user_id: str,
        category: str = "general",
        provenance: str = "user_explicit",
        confidence: float = 1.0,
    ) -> FactRecord:
        """Stores or updates a semantic fact for a user."""
        pass

    @abstractmethod
    async def delete_fact(self, key: str, user_id: str) -> bool:
        """Cryptographically deletes a specific user fact (Right to Forget)."""
        pass

    @abstractmethod
    async def search_episodic(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        """Performs semantic similarity search over episodic interaction history."""
        pass
