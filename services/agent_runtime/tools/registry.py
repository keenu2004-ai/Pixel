"""Canonical Tool Registry for Agent Capabilities."""

import logging
from typing import Any

from packages.contracts.tools import (
    ToolExecutionRequest,
    ToolExecutionResult,
    ToolSpec,
)
from packages.core.interfaces.tools import BaseTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central catalogue and dispatcher for all registered PIXEL capabilities."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register_tool(self, tool: BaseTool) -> None:
        """Registers a capability into the canonical registry."""
        name = tool.spec.name
        if name in self._tools:
            logger.warning("Overwriting existing tool registration for '%s'", name)
        self._tools[name] = tool
        logger.info("Registered capability: '%s' (Risk: %s)", name, tool.spec.risk_class)

    def get_tool(self, name: str) -> BaseTool | None:
        """Retrieves tool instance by name."""
        return self._tools.get(name)

    def get_tool_spec(self, name: str) -> ToolSpec | None:
        """Retrieves ToolSpec for a given tool name."""
        tool = self.get_tool(name)
        return tool.spec if tool else None

    def list_specs(self) -> list[ToolSpec]:
        """Returns all registered tool specifications."""
        return [t.spec for t in self._tools.values()]

    def validate_arguments(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str | None]:
        """Validates tool arguments against parameters_schema."""
        tool = self.get_tool(tool_name)
        if not tool:
            return False, f"Tool '{tool_name}' not found in registry"

        schema = tool.spec.parameters_schema
        required_fields = schema.get("required", [])

        for req in required_fields:
            if req not in arguments:
                return False, f"Missing required parameter '{req}' for tool '{tool_name}'"

        return True, None

    async def execute_tool(self, request: ToolExecutionRequest) -> ToolExecutionResult:
        """Executes a tool with argument validation and error handling."""
        tool = self.get_tool(request.tool_name)
        if not tool:
            return ToolExecutionResult(
                success=False,
                error=f"Tool '{request.tool_name}' is not registered",
            )

        # Validate arguments
        is_valid, validation_err = self.validate_arguments(request.tool_name, request.arguments)
        if not is_valid:
            return ToolExecutionResult(
                success=False,
                error=validation_err or "Argument validation failed",
            )

        try:
            return await tool.execute(request.arguments, session_id=request.session_id)
        except Exception as err:
            logger.error("Exception during execution of tool '%s': %s", request.tool_name, err)
            return ToolExecutionResult(
                success=False,
                error=f"Execution failed: {err}",
            )
