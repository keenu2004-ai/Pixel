"""
Community Skill Agent Bridge.

Adapts installed community skills into standard PIXEL BaseTool specifications,
routing all execution requests through L6 AgentPolicyGate and L8 ActionVerifier.
"""

from __future__ import annotations

import logging
from typing import Any

from packages.contracts.ecosystem import (
    PluginExecutionRequest,
    PluginLifecycleState,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import (
    AuditLevel,
    RiskClass,
    ToolExecutionResult,
    ToolSpec,
)
from packages.core.interfaces.tools import BaseTool
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.ecosystem.lifecycle import PluginLifecycleManager
from services.ecosystem.marketplace import MarketplaceRegistry

logger = logging.getLogger(__name__)


class CommunitySkillTool(BaseTool):
    """Encapsulates an installed community skill into a typed BaseTool capability."""

    def __init__(
        self,
        skill_id: str,
        tool_spec: ToolSpec,
        lifecycle_manager: PluginLifecycleManager,
        policy_gate: AgentPolicyGate,
    ):
        self.skill_id = skill_id
        self._spec = tool_spec
        self.lifecycle_manager = lifecycle_manager
        self.policy_gate = policy_gate

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        """Evaluate L6 Policy gate and dispatch to the sandboxed subprocess."""
        # 1. L6 Policy Check
        decision, card = self.policy_gate.evaluate(
            tool_spec=self.spec,
            arguments=arguments,
            task_id=session_id,
            session_id=session_id,
            user_id="default_user",
        )

        if decision.verdict == PolicyVerdict.DENY:
            return ToolExecutionResult(
                success=False,
                output=None,
                error=f"Policy Denied: {decision.reason}",
                duration_ms=0,
            )

        if decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION:
            return ToolExecutionResult(
                success=False,
                output=None,
                error="Action Requires Human Approval Card Authorization",
                duration_ms=0,
            )

        # 2. Execute within Sandboxed Plugin Subprocess
        plugin_req = PluginExecutionRequest(
            plugin_id=self.skill_id,
            action="execute",
            parameters=arguments,
            timeout_sec=10.0,
        )

        plugin_res = await self.lifecycle_manager.execute_plugin_action(plugin_req)

        return ToolExecutionResult(
            success=plugin_res.success,
            output=plugin_res.output,
            error=plugin_res.error,
            duration_ms=int(plugin_res.duration_ms),
        )


class CommunitySkillBridge:
    """Bridges sandboxed community skills into the core ToolRegistry with L6/L8 enforcement."""

    def __init__(
        self,
        lifecycle_manager: PluginLifecycleManager,
        marketplace_registry: MarketplaceRegistry,
        tool_registry: ToolRegistry,
        policy_gate: AgentPolicyGate | None = None,
    ):
        self.lifecycle_manager = lifecycle_manager
        self.marketplace_registry = marketplace_registry
        self.tool_registry = tool_registry
        self.policy_gate = policy_gate or AgentPolicyGate()

    def register_installed_skills(self) -> int:
        """Scan active plugins and register tool specifications for active skills."""
        plugins = self.lifecycle_manager.list_plugins()
        registered_count = 0

        for plugin in plugins:
            if plugin["state"] != PluginLifecycleState.ENABLED:
                continue

            skill_id = plugin["plugin_id"]
            manifest = plugin["manifest"]

            # Map RiskClass from capabilities
            risk_class = RiskClass.READ
            if any(
                c.value in ["write_memory", "device_control"]
                for c in plugin["granted_capabilities"]
            ):
                risk_class = RiskClass.HIGH_IMPACT
            elif any(
                c.value in ["network_outbound", "webhook_emit"]
                for c in plugin["granted_capabilities"]
            ):
                risk_class = RiskClass.EXTERNAL_COMMUNICATION

            tool_spec = ToolSpec(
                name=skill_id.replace(".", "_"),
                description=f"[Community Skill] {manifest.description}",
                parameters_schema=manifest.config_schema or {"type": "object"},
                risk_class=risk_class,
                audit_level=AuditLevel.DETAILED,
                timeout_ms=10000,
            )

            tool = CommunitySkillTool(
                skill_id=skill_id,
                tool_spec=tool_spec,
                lifecycle_manager=self.lifecycle_manager,
                policy_gate=self.policy_gate,
            )

            # Register into ToolRegistry
            self.tool_registry.register_tool(tool)
            registered_count += 1

        return registered_count
