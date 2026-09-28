"""Unit tests for Fleet Tools and Operations Manager."""

from services.control_plane.manager import ControlPlaneManager
from services.fleet.manager import FleetOperationsManager


def test_fleet_operations_manager_facade() -> None:
    """Verify FleetOperationsManager facade initializations, topology, and tool registry registration."""
    mgr = FleetOperationsManager()
    assert mgr.node_manager is not None
    assert mgr.model_registry is not None
    assert mgr.routing_engine is not None
    assert mgr.scheduler is not None
    assert mgr.kill_switches is not None
    assert mgr.mission_governor is not None
    assert len(mgr.tools) == 5

    # Central authority node should be seeded
    nodes = mgr.node_manager.list_active_nodes()
    assert len(nodes) >= 1
    assert nodes[0].identity.is_central_authority is True


def test_control_plane_manager_fleet_integration() -> None:
    """Verify that ControlPlaneManager registers fleet tools and initializes fleet manager."""
    cp_mgr = ControlPlaneManager()
    assert cp_mgr.fleet_manager is not None

    assert cp_mgr.tool_registry.get_tool("get_fleet_topology") is not None
    assert cp_mgr.tool_registry.get_tool("discover_node_capabilities") is not None
    assert cp_mgr.tool_registry.get_tool("delegate_fleet_task") is not None
    assert cp_mgr.tool_registry.get_tool("cancel_fleet_task") is not None
    assert cp_mgr.tool_registry.get_tool("revoke_fleet_node") is not None
