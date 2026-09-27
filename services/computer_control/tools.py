"""Computer Control and Desktop Automation Tools.

Provides typed L5 tool wrappers around DesktopAdapter for window management,
focus switching, clipboard interaction, and visual inspection.
"""

import time
from typing import Any

from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.computer_control.desktop_adapter import DesktopAdapter


class ListWindowsTool(BaseTool):
    """Tool for listing open application windows on the desktop."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="list_windows",
            description="Lists all open visible application windows and their titles/bounds.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {},
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        windows = self.adapter.list_windows()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[w.model_dump() for w in windows],
            duration_ms=duration_ms,
            evidence={"window_count": len(windows)},
        )


class GetActiveWindowTool(BaseTool):
    """Tool for retrieving the currently active/focused desktop window."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_active_window",
            description="Returns metadata of the currently focused desktop application window.",
            risk_class=RiskClass.READ,
            parameters_schema={"type": "object", "properties": {}},
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        active_win = self.adapter.get_active_window()
        duration_ms = int((time.perf_counter() - start) * 1000)

        if not active_win:
            return ToolExecutionResult(
                success=False,
                error="No active window found",
                duration_ms=duration_ms,
            )

        return ToolExecutionResult(
            success=True,
            output=active_win.model_dump(),
            duration_ms=duration_ms,
            evidence={"title": active_win.title, "app_name": active_win.app_name},
        )


class FocusWindowTool(BaseTool):
    """Tool for focusing an application window by title or process name."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="focus_window",
            description="Brings a desktop application window to the foreground by title or app name.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Title, app name, or window ID to focus"},
                },
                "required": ["query"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        query = arguments.get("query", "")
        success = self.adapter.focus_window(query)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=success,
            output={"focused": success, "query": query},
            error=None if success else f"Window matching '{query}' not found or could not be focused",
            duration_ms=duration_ms,
            evidence={"query": query, "focused": success},
        )


class ReadClipboardTool(BaseTool):
    """Tool for reading textual contents of system clipboard."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_clipboard",
            description="Reads the current text content from the system clipboard.",
            risk_class=RiskClass.READ,
            parameters_schema={"type": "object", "properties": {}},
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        data = self.adapter.read_clipboard()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=data.model_dump(),
            duration_ms=duration_ms,
            evidence={"length": data.length},
        )


class WriteClipboardTool(BaseTool):
    """Tool for writing text content into system clipboard."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="write_clipboard",
            description="Copies text into the system clipboard.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text content to copy to clipboard"},
                },
                "required": ["text"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        text = arguments.get("text", "")
        success = self.adapter.write_clipboard(text)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=success,
            output={"copied": success, "length": len(text)},
            duration_ms=duration_ms,
            evidence={"length": len(text)},
        )


class CaptureWindowTool(BaseTool):
    """Tool for capturing screenshot of a target window or active display."""

    def __init__(self, adapter: DesktopAdapter) -> None:
        self.adapter = adapter

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="capture_window",
            description="Captures visual state of active window or query window with privacy redaction.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Optional window title or app name"},
                    "redact": {"type": "boolean", "default": True, "description": "Whether to mask sensitive visual areas"},
                },
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.DETAILED,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        query = arguments.get("query")
        redact = arguments.get("redact", True)
        capture = self.adapter.capture_window(query=query, redact=redact)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=capture.model_dump(),
            duration_ms=duration_ms,
            evidence={
                "capture_id": capture.capture_id,
                "app_name": capture.app_name,
                "dimensions": f"{capture.width}x{capture.height}",
                "is_redacted": capture.is_redacted,
            },
        )
