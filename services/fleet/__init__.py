"""PIXEL — Phase 17 Edge AI Swarm Deployment & Autonomous Fleet Operations Package.

Exports node management, model distribution, multi-signal routing, distributed scheduling,
memory coordination, failure recovery, kill switches, and fleet tools.
"""

from services.fleet.distributed_memory import FleetMemoryCoordinator
from services.fleet.failure_recovery import FleetFailureRecoveryEngine
from services.fleet.kill_switches import FleetKillSwitchManager
from services.fleet.manager import FleetOperationsManager
from services.fleet.mission_governor import AutonomousFleetMissionGovernor
from services.fleet.model_registry import FleetModelRegistry
from services.fleet.multimodal_edge import EdgeMultimodalCoordinator
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.resource_governor import FleetResourceGovernor
from services.fleet.routing_engine import FleetRoutingEngine
from services.fleet.scheduler import FleetScheduler
from services.fleet.tools import (
    CancelFleetTaskTool,
    DelegateFleetTaskTool,
    DiscoverNodeCapabilitiesTool,
    GetFleetTopologyTool,
    RevokeFleetNodeTool,
)

__all__ = [
    "EdgeNodeManager",
    "FleetModelRegistry",
    "FleetResourceGovernor",
    "FleetRoutingEngine",
    "FleetScheduler",
    "FleetMemoryCoordinator",
    "EdgeMultimodalCoordinator",
    "FleetFailureRecoveryEngine",
    "FleetKillSwitchManager",
    "AutonomousFleetMissionGovernor",
    "FleetOperationsManager",
    "GetFleetTopologyTool",
    "DiscoverNodeCapabilitiesTool",
    "DelegateFleetTaskTool",
    "CancelFleetTaskTool",
    "RevokeFleetNodeTool",
]
