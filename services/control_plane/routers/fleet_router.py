"""PIXEL — Control Plane Fleet & Edge AI Swarm Router.

Exposes REST APIs for:
1. Fleet Node Inventory, Topology & Discovery
2. Node Enrollment & PKI Verification
3. Real-Time Resource & Heartbeat Telemetry
4. Multi-Signal Task Routing & Delegation
5. Model Distribution & Cache Governance
6. Distributed Leases, Checkpoints & Cancellation
7. Node Quarantine, Revocation & Emergency Kill Switches
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.fleet import (
    EdgeNode,
    FleetCapability,
    FleetDataClassification,
    FleetKillSwitchDomain,
    FleetModelSpec,
    HardwareProfile,
    ResourceProfile,
    RoutingDecision,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager
from services.fleet.manager import FleetOperationsManager

router = APIRouter(prefix="/api/v1/fleet", tags=["Fleet & Edge AI Swarm"])


class EnrollNodeRequest(BaseModel):
    node_id: str
    node_name: str
    device_type: str = "DESKTOP"
    capabilities: list[FleetCapability] = [FleetCapability.CPU]
    hardware: HardwareProfile | None = None
    is_central_authority: bool = False


class NodeHeartbeatRequest(BaseModel):
    resources: ResourceProfile | None = None


class RouteTaskRequest(BaseModel):
    task_id: str = "task_01"
    required_capability: FleetCapability
    source_node_id: str
    data_classification: FleetDataClassification = FleetDataClassification.LOW_SENSITIVITY
    is_heavy_task: bool = False


class DelegateTaskRequest(BaseModel):
    goal_description: str
    capability: FleetCapability
    source_node_id: str
    data_classification: FleetDataClassification = FleetDataClassification.LOW_SENSITIVITY
    is_heavy_task: bool = False


class QuarantineNodeRequest(BaseModel):
    reason: str


class ToggleKillSwitchRequest(BaseModel):
    domain: FleetKillSwitchDomain
    active: bool
    reason: str = ""


def _get_fleet_manager(manager: ControlPlaneManager) -> FleetOperationsManager:
    if hasattr(manager, "fleet_manager") and manager.fleet_manager:
        return manager.fleet_manager
    return FleetOperationsManager()


@router.get("/nodes", response_model=list[EdgeNode])
async def list_fleet_nodes(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    active_only: Annotated[bool, Query()] = False,
    capability: Annotated[FleetCapability | None, Query()] = None,
) -> list[EdgeNode]:
    """Retrieves all registered edge nodes in the fleet topology."""
    fm = _get_fleet_manager(manager)
    return fm.node_manager.list_nodes(active_only=active_only, capability_filter=capability)


@router.post("/nodes/enroll", response_model=EdgeNode)
async def enroll_edge_node(
    req: EnrollNodeRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> EdgeNode:
    """Enrolls a new edge node with PKI identity verification."""
    fm = _get_fleet_manager(manager)
    try:
        return fm.node_manager.enroll_node(
            node_id=req.node_id,
            node_name=req.node_name,
            device_type=req.device_type,
            capabilities=req.capabilities,
            hardware=req.hardware,
            is_central_authority=req.is_central_authority,
        )
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/nodes/{node_id}/heartbeat")
async def record_node_heartbeat(
    node_id: str,
    req: NodeHeartbeatRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Updates edge node heartbeat timestamp and resource metrics."""
    fm = _get_fleet_manager(manager)
    ok = fm.node_manager.record_heartbeat(node_id=node_id, resources=req.resources)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Node '{node_id}' not found or revoked.")
    return {"success": True, "node_id": node_id}


@router.post("/nodes/{node_id}/quarantine")
async def quarantine_edge_node(
    node_id: str,
    req: QuarantineNodeRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Isolates a suspicious edge node and revokes its task leases."""
    fm = _get_fleet_manager(manager)
    ok = fm.failure_recovery.detect_and_isolate_malicious_node(
        node_id=node_id, violation_type=req.reason
    )
    if not ok:
        raise HTTPException(status_code=400, detail=f"Cannot quarantine node '{node_id}'.")
    return {"success": True, "quarantined_node": node_id, "reason": req.reason}


@router.delete("/nodes/{node_id}")
async def revoke_edge_node(
    node_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    reason: Annotated[str, Query()] = "Admin revocation",
) -> dict[str, Any]:
    """Permanently revokes an edge node's certificate and severs fleet credentials."""
    fm = _get_fleet_manager(manager)
    ok = fm.node_manager.revoke_node(node_id=node_id, reason=reason)
    if not ok:
        raise HTTPException(status_code=400, detail=f"Cannot revoke node '{node_id}'.")
    return {"success": True, "revoked_node": node_id}


@router.get("/models", response_model=list[FleetModelSpec])
async def list_fleet_models(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    capability: Annotated[FleetCapability | None, Query()] = None,
) -> list[FleetModelSpec]:
    """Lists distributable models in the fleet registry."""
    fm = _get_fleet_manager(manager)
    return fm.model_registry.list_models(capability=capability)


@router.post("/tasks/route", response_model=RoutingDecision)
async def calculate_task_routing(
    req: RouteTaskRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> RoutingDecision:
    """Calculates multi-signal task placement with transparent explanation."""
    fm = _get_fleet_manager(manager)
    try:
        return fm.routing_engine.route_task(
            task_id=req.task_id,
            required_capability=req.required_capability,
            source_node_id=req.source_node_id,
            data_classification=req.data_classification,
            is_heavy_task=req.is_heavy_task,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/tasks/delegate")
async def delegate_fleet_task(
    req: DelegateTaskRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Routes and delegates a workload to the optimal edge node."""
    fm = _get_fleet_manager(manager)
    try:
        envelope, lease, decision = fm.delegate_task(
            goal_description=req.goal_description,
            capability=req.capability,
            source_node_id=req.source_node_id,
            data_classification=req.data_classification,
            is_heavy_task=req.is_heavy_task,
        )
        return {
            "success": True,
            "envelope": envelope.model_dump(),
            "lease": lease.model_dump(),
            "routing_decision": decision.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/tasks/{task_id}/cancel")
async def cancel_fleet_task(
    task_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Propagates cancellation of a distributed fleet task and revokes active leases."""
    fm = _get_fleet_manager(manager)
    cancelled = fm.scheduler.cancel_task(task_id=task_id)
    return {"success": cancelled, "task_id": task_id}


@router.get("/killswitches")
async def list_kill_switches(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Lists currently active fleet kill switches."""
    fm = _get_fleet_manager(manager)
    return {"active_kill_switches": fm.kill_switches.list_active_kill_switches()}


@router.post("/killswitches/toggle")
async def toggle_kill_switch(
    req: ToggleKillSwitchRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Engages or disengages a fleet emergency kill switch domain."""
    fm = _get_fleet_manager(manager)
    if req.active:
        fm.kill_switches.activate_kill_switch(domain=req.domain, reason=req.reason)
    else:
        fm.kill_switches.deactivate_kill_switch(domain=req.domain)
    return {"domain": req.domain.value, "is_active": req.active}
