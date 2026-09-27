"""Abstract Interface for Registered Capabilities and Tools."""

from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.tools import ToolExecutionResult, ToolSpec


class BaseTool(ABC):
    """Abstract base class for all typed PIXEL tools and capabilities."""

    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        """Returns the typed specification and risk classification for this tool."""
        pass

    @abstractmethod
    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        """Executes the tool with validated arguments."""
        pass
