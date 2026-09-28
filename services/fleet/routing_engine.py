"""PIXEL — Phase 17 Fleet Intelligent Multi-Signal Routing Engine.

Evaluates capability matching, 5-tier privacy classifications, latency budgets,
battery conservation, thermal state, and network health to route tasks to the optimal node.
"""

from packages.contracts.fleet import (
    EdgeNode,
    FleetCapability,
    FleetDataClassification,
    NetworkCondition,
    RoutingDecision,
)
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.resource_governor import FleetResourceGovernor


class FleetRoutingEngine:
    """Calculates optimal edge task placement with full transparency and safety invariants."""

    def __init__(
        self,
        node_manager: EdgeNodeManager,
        resource_governor: FleetResourceGovernor | None = None,
    ) -> None:
        self._node_manager = node_manager
        self._governor = resource_governor or FleetResourceGovernor()

    def route_task(
        self,
        task_id: str,
        required_capability: FleetCapability,
        source_node_id: str,
        data_classification: FleetDataClassification = FleetDataClassification.LOW_SENSITIVITY,
        is_heavy_task: bool = False,
    ) -> RoutingDecision:
        """Determines optimal node placement for a fleet task."""
        source_node = self._node_manager.get_node(source_node_id)
        all_nodes = self._node_manager.list_nodes(active_only=True)

        # 1. Privacy Invariant Rule 24: HIGHLY_SENSITIVE data NEVER leaves local node
        if data_classification == FleetDataClassification.HIGHLY_SENSITIVE:
            if source_node and required_capability in source_node.capabilities:
                return RoutingDecision(
                    task_id=task_id,
                    selected_node_id=source_node_id,
                    target_capability=required_capability,
                    data_classification=data_classification,
                    execution_tier="LOCAL",
                    reason="Highly sensitive data classification strictly requires local-only execution.",
                    estimated_latency_ms=2.0,
                    battery_cost_tier="MEDIUM",
                    confidence=1.0,
                )
            raise PermissionError(
                "Highly sensitive task cannot be routed remotely and local node lacks capability."
            )

        # 2. Offline / Partition Handling
        if source_node and source_node.resources.network_condition == NetworkCondition.OFFLINE:
            if required_capability in source_node.capabilities:
                return RoutingDecision(
                    task_id=task_id,
                    selected_node_id=source_node_id,
                    target_capability=required_capability,
                    data_classification=data_classification,
                    execution_tier="LOCAL",
                    reason="Source node is offline; executing on local fallback capability.",
                    estimated_latency_ms=5.0,
                    battery_cost_tier="LOW",
                    confidence=0.90,
                )
            raise ConnectionError(
                f"Node '{source_node_id}' is offline and lacks capability '{required_capability.value}'."
            )

        # 3. Battery Conservation Offloading
        # If source is battery-constrained, prioritize capable desktop/server node
        if (
            source_node
            and is_heavy_task
            and source_node.resources.battery_level_percent is not None
            and source_node.resources.battery_level_percent < 25.0
            and not source_node.resources.is_charging
        ):
            for candidate in all_nodes:
                if (
                    candidate.identity.node_id != source_node_id
                    and required_capability in candidate.capabilities
                ):
                    can_accept, _ = self._governor.can_accept_workload(
                        candidate, required_capability, is_heavy_task
                    )
                    if can_accept:
                        return RoutingDecision(
                            task_id=task_id,
                            selected_node_id=candidate.identity.node_id,
                            target_capability=required_capability,
                            data_classification=data_classification,
                            execution_tier="DISTRIBUTED",
                            reason=f"Offloaded to '{candidate.identity.node_name}' to conserve low battery ({source_node.resources.battery_level_percent:.1f}%) on source node.",
                            estimated_latency_ms=candidate.resources.rtt_to_authority_ms + 15.0,
                            battery_cost_tier="LOW",
                            confidence=0.98,
                            fallback_node_id=source_node_id,
                        )

        # 4. Local Execution Preference for Low Latency
        if source_node and required_capability in source_node.capabilities:
            can_run_local, _ = self._governor.can_accept_workload(
                source_node, required_capability, is_heavy_task
            )
            if can_run_local:
                return RoutingDecision(
                    task_id=task_id,
                    selected_node_id=source_node_id,
                    target_capability=required_capability,
                    data_classification=data_classification,
                    execution_tier="LOCAL",
                    reason="Executed on local node for minimum latency and zero network exposure.",
                    estimated_latency_ms=2.0,
                    battery_cost_tier="LOW",
                    confidence=0.99,
                )

        # 5. Distributed Fleet Placement (Least-loaded capable node)
        candidates: list[EdgeNode] = []
        for n in all_nodes:
            if required_capability in n.capabilities:
                can_accept, _ = self._governor.can_accept_workload(
                    n, required_capability, is_heavy_task
                )
                if can_accept:
                    candidates.append(n)

        if not candidates:
            # Central fallback if available
            central_nodes = [n for n in all_nodes if n.identity.is_central_authority]
            if central_nodes:
                c_node = central_nodes[0]
                return RoutingDecision(
                    task_id=task_id,
                    selected_node_id=c_node.identity.node_id,
                    target_capability=required_capability,
                    data_classification=data_classification,
                    execution_tier="CENTRAL",
                    reason="Defaulted to central authority node as fallback.",
                    estimated_latency_ms=c_node.resources.rtt_to_authority_ms + 25.0,
                    battery_cost_tier="LOW",
                    confidence=0.85,
                )
            raise RuntimeError(
                f"No capable fleet node available for task capability '{required_capability.value}'."
            )

        # Sort candidates by active task count (least loaded) and latency
        candidates.sort(
            key=lambda x: (x.resources.active_task_count, x.resources.rtt_to_authority_ms)
        )
        best_node = candidates[0]

        return RoutingDecision(
            task_id=task_id,
            selected_node_id=best_node.identity.node_id,
            target_capability=required_capability,
            data_classification=data_classification,
            execution_tier="DISTRIBUTED",
            reason=f"Selected least-loaded capable edge node '{best_node.identity.node_name}' (RTT: {best_node.resources.rtt_to_authority_ms:.1f}ms).",
            estimated_latency_ms=best_node.resources.rtt_to_authority_ms + 10.0,
            battery_cost_tier="LOW",
            confidence=0.96,
            fallback_node_id=source_node_id,
        )
