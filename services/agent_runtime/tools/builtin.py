"""Standard Built-in Capabilities for PIXEL Agent Runtime."""

import logging
import os
from pathlib import Path
from typing import Any

from packages.contracts.tools import (
    AuditLevel,
    RiskClass,
    ToolExecutionResult,
    ToolSpec,
)
from packages.core.interfaces.os_adapter import BaseOSAdapter
from packages.core.interfaces.tools import BaseTool
from services.memory.manager import MemoryManager
from services.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. Filesystem Tools (Sandbox Enforced)
# ---------------------------------------------------------------------------


class ReadFileTool(BaseTool):
    """Reads content of a local text file within permitted directories."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_file",
            description="Reads the text contents of a specified local file.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the file to read"}
                },
                "required": ["path"],
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        file_path = str(arguments.get("path", "")).strip()
        path = Path(file_path)

        if not path.exists():
            return ToolExecutionResult(success=False, error=f"File not found: '{file_path}'")
        if not path.is_file():
            return ToolExecutionResult(
                success=False, error=f"Path is not a regular file: '{file_path}'"
            )

        try:
            content = path.read_text(encoding="utf-8")
            return ToolExecutionResult(
                success=True,
                output=content,
                evidence={"path": str(path.resolve()), "size_bytes": len(content.encode("utf-8"))},
            )
        except Exception as err:
            return ToolExecutionResult(success=False, error=f"Failed to read file: {err}")


class WriteFileTool(BaseTool):
    """Writes or overwrites text content to a local file."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="write_file",
            description="Writes text content to a specified local file. Reversible and sandboxed.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path"},
                    "content": {"type": "string", "description": "Text content to write"},
                },
                "required": ["path", "content"],
            },
            audit_level=AuditLevel.DETAILED,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        file_path = str(arguments.get("path", "")).strip()
        content = str(arguments.get("content", ""))
        path = Path(file_path)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return ToolExecutionResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {file_path}",
                evidence={
                    "path": str(path.resolve()),
                    "size_bytes": len(content.encode("utf-8")),
                    "exists": True,
                },
            )
        except Exception as err:
            return ToolExecutionResult(success=False, error=f"Failed to write file: {err}")


class ListDirectoryTool(BaseTool):
    """Lists files and folders in a local directory."""

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_directory",
            description="Lists all files and subdirectories within a folder.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list",
                        "default": ".",
                    }
                },
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        dir_path = str(arguments.get("path", ".")).strip() or "."
        path = Path(dir_path)

        if not path.exists() or not path.is_dir():
            return ToolExecutionResult(success=False, error=f"Directory not found: '{dir_path}'")

        try:
            items = [
                {
                    "name": item.name,
                    "is_dir": item.is_dir(),
                    "size": item.stat().st_size if item.is_file() else 0,
                }
                for item in path.iterdir()
            ]
            return ToolExecutionResult(
                success=True,
                output=items,
                evidence={"count": len(items), "directory": str(path.resolve())},
            )
        except Exception as err:
            return ToolExecutionResult(success=False, error=f"Failed to list directory: {err}")


# ---------------------------------------------------------------------------
# 2. OS & System Capabilities
# ---------------------------------------------------------------------------


class SetVolumeTool(BaseTool):
    """Adjusts OS master volume level."""

    def __init__(self, os_adapter: BaseOSAdapter) -> None:
        self.os_adapter = os_adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="set_volume",
            description="Sets master audio volume percentage (0-100).",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "level": {
                        "type": "integer",
                        "description": "Target volume level (0 to 100)",
                        "minimum": 0,
                        "maximum": 100,
                    }
                },
                "required": ["level"],
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        level = int(arguments.get("level", 50))
        vol = await self.os_adapter.set_volume(level)
        return ToolExecutionResult(
            success=True,
            output=f"Volume adjusted to {vol}%",
            evidence={"level": vol},
        )


class LaunchAppTool(BaseTool):
    """Launches an allowlisted local desktop application."""

    def __init__(self, os_adapter: BaseOSAdapter) -> None:
        self.os_adapter = os_adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="launch_app",
            description="Opens an allowlisted desktop application (e.g. notepad, calc, browser).",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name of the application to launch",
                    }
                },
                "required": ["app_name"],
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        app_name = str(arguments.get("app_name", "")).strip()
        success = await self.os_adapter.launch_app(app_name)
        return ToolExecutionResult(
            success=success,
            output=f"Launched '{app_name}'" if success else f"Could not launch '{app_name}'",
            evidence={"app_name": app_name, "launched": success},
        )


class GetSystemInfoTool(BaseTool):
    """Retrieves OS and battery / power telemetry."""

    def __init__(self, os_adapter: BaseOSAdapter) -> None:
        self.os_adapter = os_adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_system_info",
            description="Queries battery percentage, power status, and OS platform information.",
            risk_class=RiskClass.READ,
            parameters_schema={"type": "object", "properties": {}},
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        battery = await self.os_adapter.get_battery_status()
        time_now = await self.os_adapter.get_system_time()
        return ToolExecutionResult(
            success=True,
            output={"battery": battery, "system_time": time_now.isoformat(), "platform": os.name},
            evidence={"battery": battery, "platform": os.name},
        )


# ---------------------------------------------------------------------------
# 3. Knowledge & Memory Tools
# ---------------------------------------------------------------------------


class QueryMemoryTool(BaseTool):
    """Queries user semantic facts and episodic interaction history."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="query_memory",
            description="Queries user preferences, long-term facts, and previous interaction history.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query for memory context"},
                    "user_id": {
                        "type": "string",
                        "description": "Target user ID",
                        "default": "default_user",
                    },
                },
                "required": ["query"],
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        query = str(arguments.get("query", "")).strip()
        user_id = str(arguments.get("user_id", "default_user"))
        context = await self.memory_manager.query_context(
            query=query, session_id=session_id, user_id=user_id
        )
        return ToolExecutionResult(
            success=True,
            output=context,
            evidence={
                "facts_count": len(context.get("facts", [])),
                "episodes_count": len(context.get("episodes", [])),
            },
        )


class SearchKnowledgeTool(BaseTool):
    """Performs hybrid vector & keyword retrieval over technical documentation."""

    def __init__(self, rag_retriever: RAGRetriever) -> None:
        self.rag_retriever = rag_retriever

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_knowledge",
            description="Performs hybrid dense vector and keyword search over technical documentation and indexed code.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {
                        "type": "integer",
                        "description": "Number of items to retrieve",
                        "default": 3,
                    },
                },
                "required": ["query"],
            },
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        query = str(arguments.get("query", "")).strip()
        top_k = int(arguments.get("top_k", 3))
        context = await self.rag_retriever.retrieve_and_assemble(query=query, top_k=top_k)
        return ToolExecutionResult(
            success=True,
            output={"formatted_context": context.formatted_context, "citations": context.citations},
            evidence={"total_chunks": len(context.retrieved_items)},
        )
