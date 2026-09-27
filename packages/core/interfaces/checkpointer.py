"""Abstract Checkpointer Interface for Agent State Persistence."""

from abc import ABC, abstractmethod

from packages.contracts.agent import AgentCheckpoint, AgentState


class BaseCheckpointer(ABC):
    """Abstract base class for saving and restoring agent state across crashes and approval pauses."""

    @abstractmethod
    async def save_checkpoint(self, state: AgentState, version: int = 1) -> str:
        """Persists agent state checkpoint and returns checkpoint ID."""
        pass

    @abstractmethod
    async def get_latest_checkpoint(self, task_id: str) -> AgentState | None:
        """Retrieves and deserializes the latest state for a given task ID."""
        pass

    @abstractmethod
    async def list_checkpoints(self, task_id: str) -> list[AgentCheckpoint]:
        """Lists all persisted checkpoint records for a task."""
        pass

    @abstractmethod
    async def delete_checkpoints(self, task_id: str) -> bool:
        """Deletes all checkpoints for a completed/purged task."""
        pass
