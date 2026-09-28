"""PIXEL — Phase 17 Fleet Capability Tools (L5 Tool Registry).

Provides typed L5 tool wrappers for Fleet Topology, Capability Discovery,
Task Delegation, Task Cancellation, Model Querying, Node Revocation, and Health.
"""

import time
from typing import Any

from packages.contracts.fleet import FleetCapability, FleetDataClassification
from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.routing_engine import FleetRoutingEngine
from services.fleet.scheduler import FleetScheduler


class GetFleetTopologyTool(BaseTool):
    """Tool to inspect active edge nodes and topology in the fleet."""

    def __init__(self, node_manager: EdgeNodeManager) -> None:
        self._node_manager = node_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="get_fleet_topology",
            description="Returns all registered edge nodes, health states, and resource headroom.",
            risk_class=RiskClass.READ,
            parameters_schema={"type": "object", "properties": {}},
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        nodes = self._node_manager.list_nodes()
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[n.model_dump() for n in nodes],
            duration_ms=duration_ms,
            evidence={"node_count": len(nodes)},
        )


class DiscoverNodeCapabilitiesTool(BaseTool):
    """Tool to discover verified hardware and software capabilities of edge nodes."""

    def __init__(self, node_manager: EdgeNodeManager) -> None:
        self._node_manager = node_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="discover_node_capabilities",
            description="Finds fleet nodes providing a specific hardware or model capability.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "capability": {"type": "string"},
                },
                "required": ["capability"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        cap_str = arguments["capability"]
        cap = FleetCapability(cap_str) if cap_str in FleetCapability.__members__ else None
        nodes = self._node_manager.list_nodes(capability_filter=cap)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[n.model_dump() for n in nodes],
            duration_ms=duration_ms,
            evidence={"matching_nodes": len(nodes)},
        )


class DelegateFleetTaskTool(BaseTool):
    """Tool to intelligently route and delegate a task to an edge node."""

    def __init__(
        self,
        routing_engine: FleetRoutingEngine,
        scheduler: FleetScheduler,
    ) -> None:
        self._router = routing_engine
        self._scheduler = scheduler

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="delegate_fleet_task",
            description="Routes and delegates a workload to the optimal edge node under central authority.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "goal_description": {"type": "string"},
                    "capability_required": {"type": "string"},
                    "source_node_id": {"type": "string"},
                    "data_classification": {"type": "string", "default": "LOW_SENSITIVITY"},
                },
                "required": ["goal_description", "capability_required", "source_node_id"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.DETAILED,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        cap_str = arguments["capability_required"]
        cap = (
            FleetCapability(cap_str)
            if cap_str in FleetCapability.__members__
            else FleetCapability.CPU
        )
        class_str = arguments.get("data_classification", "LOW_SENSITIVITY")
        data_class = (
            FleetDataClassification(class_str)
            if class_str in FleetDataClassification.__members__
            else FleetDataClassification.LOW_SENSITIVITY
        )

        decision = self._router.route_task(
            task_id="task_del_01",
            required_capability=cap,
            source_node_id=arguments["source_node_id"],
            data_classification=data_class,
        )

        envelope = self._scheduler.create_delegation_envelope(
            goal_description=arguments["goal_description"],
            capability_required=cap,
            source_node_id=arguments["source_node_id"],
            target_node_id=decision.selected_node_id,
            data_classification=data_class,
        )

        lease = self._scheduler.grant_lease(
            task_id=envelope.task_id, node_id=decision.selected_node_id
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output={
                "routing_decision": decision.model_dump(),
                "envelope": envelope.model_dump(),
                "lease_id": lease.lease_id,
            },
            duration_ms=duration_ms,
            evidence={
                "selected_node": decision.selected_node_id,
                "execution_tier": decision.execution_tier,
            },
        )


class CancelFleetTaskTool(BaseTool):
    """Tool to cancel an active fleet task across all nodes."""

    def __init__(self, scheduler: FleetScheduler) -> None:
        self._scheduler = scheduler

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="cancel_fleet_task",
            description="Propagates cancellation of a distributed task and revokes worker execution leases.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                },
                "required": ["task_id"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        cancelled = self._scheduler.cancel_task(arguments["task_id"])
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=cancelled,
            output={"task_id": arguments["task_id"], "cancelled": cancelled},
            duration_ms=duration_ms,
        )


class RevokeFleetNodeTool(BaseTool):
    """Tool to permanently revoke an edge node from the fleet."""

    def __init__(self, node_manager: EdgeNodeManager) -> None:
        self._node_manager = node_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="revoke_fleet_node",
            description="Permanently revokes an edge node's certificate and severs its fleet access.",
            risk_class=RiskClass.HIGH_IMPACT,
            parameters_schema={
                "type": "object",
                "properties": {
                    "node_id": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["node_id"],
            },
            timeout_ms=5000,
            requires_approval=True,  # High impact requires explicit user approval
            audit_level=AuditLevel.CRYPTOGRAPHIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        revoked = self._node_manager.revoke_node(
            node_id=arguments["node_id"],
            reason=arguments.get("reason", "Admin revocation"),
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=revoked,
            output={"node_id": arguments["node_id"], "revoked": revoked},
            duration_ms=duration_ms,
        )
