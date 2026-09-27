"""PIXEL — Real-World Capability Tool Wrappers for Canonical ToolRegistry.

Exposes typed BaseTool implementations for:
- Sandboxed Filesystem (Read, Write, List, Delete)
- Controlled Terminal Execution
- Sandboxed Browser Automation
- Real Android Native Actions
"""

import logging
from typing import TYPE_CHECKING, Any

from packages.contracts.mobile import AndroidActionPayload, AndroidActionType
from packages.contracts.tools import (
    RiskClass,
    ToolExecutionResult,
    ToolSpec,
)
from packages.core.interfaces.tools import BaseTool
from services.computer_control.browser_tool import ControlledBrowserTool
from services.os_control.filesystem_tool import SafeFilesystemTool
from services.os_control.terminal_tool import TerminalTool

if TYPE_CHECKING:
    pass

logger = logging.getLogger("pixel.agent_runtime.tools.real_world")


class FilesystemReadTool(BaseTool):
    """Tool wrapper for sandboxed file reading."""

    def __init__(self, fs: SafeFilesystemTool | None = None) -> None:
        self.fs = fs or SafeFilesystemTool()
        self._spec = ToolSpec(
            name="filesystem_read",
            description="Reads contents of a file within sandboxed workspace.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {"file_path": {"type": "string"}},
                "required": ["file_path"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        path = str(arguments.get("file_path", ""))
        res = self.fs.read_file(path, session_id=session_id)
        return ToolExecutionResult(
            success=res.success,
            output=res.content if res.success else None,
            error=res.error,
        )


class FilesystemWriteTool(BaseTool):
    """Tool wrapper for sandboxed file writing."""

    def __init__(self, fs: SafeFilesystemTool | None = None) -> None:
        self.fs = fs or SafeFilesystemTool()
        self._spec = ToolSpec(
            name="filesystem_write",
            description="Writes text content to a sandboxed file.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["file_path", "content"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        path = str(arguments.get("file_path", ""))
        content = str(arguments.get("content", ""))
        res = self.fs.write_file(path, content, session_id=session_id)
        return ToolExecutionResult(
            success=res.success,
            output=f"Successfully written {res.size_bytes} bytes to {path}"
            if res.success
            else None,
            error=res.error,
        )


class TerminalRunTool(BaseTool):
    """Tool wrapper for controlled terminal execution."""

    def __init__(self, terminal: TerminalTool | None = None) -> None:
        self.terminal = terminal or TerminalTool()
        self._spec = ToolSpec(
            name="terminal_run_command",
            description="Executes a shell command in a controlled subprocess with secret scrubbing.",
            risk_class=RiskClass.HIGH_IMPACT,
            parameters_schema={
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        cmd = str(arguments.get("command", ""))
        res = await self.terminal.run_command(cmd, session_id=session_id)
        return ToolExecutionResult(
            success=res.exit_code == 0,
            output=res.stdout if res.exit_code == 0 else res.stderr,
            error=res.stderr if res.exit_code != 0 else None,
        )


class BrowserNavigateTool(BaseTool):
    """Tool wrapper for controlled browser navigation."""

    def __init__(self, browser: ControlledBrowserTool | None = None) -> None:
        self.browser = browser or ControlledBrowserTool()
        self._spec = ToolSpec(
            name="browser_navigate",
            description="Navigates browser to URL and returns page title and text.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        url = str(arguments.get("url", ""))
        res = await self.browser.navigate(url, session_id=session_id)
        return ToolExecutionResult(
            success=res.success,
            output=f"Page [{res.page_title}]: {res.extracted_text}" if res.success else None,
            error=res.error,
        )


class AndroidActionTool(BaseTool):
    """Tool wrapper for native Android intents and actions."""

    def __init__(self, adapter: Any | None = None) -> None:
        if adapter is None:
            from services.voice_gateway.android_actions import AndroidActionAdapter

            self.adapter = AndroidActionAdapter()
        else:
            self.adapter = adapter
        self._spec = ToolSpec(
            name="android_action",
            description="Dispatches native Android intents for calls, messages, alarms, timers, and media.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "action_type": {"type": "string"},
                    "parameters": {"type": "object"},
                },
                "required": ["action_type"],
            },
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        action_type_str = str(arguments.get("action_type", "MEDIA_CONTROL"))
        params = arguments.get("parameters", {})
        try:
            action_type = AndroidActionType(action_type_str)
        except ValueError:
            return ToolExecutionResult(
                success=False,
                error=f"Invalid Android action_type: {action_type_str}",
            )

        payload = AndroidActionPayload(
            action_type=action_type,
            parameters=params,
        )
        res = await self.adapter.execute_action(payload, session_id=session_id)
        return ToolExecutionResult(
            success=res.success,
            output=str(res.result_data) if res.success else None,
            error=res.error_message,
        )
