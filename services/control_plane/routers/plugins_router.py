"""
Plugins Management REST API Router.

Governs plugin discovery, lifecycle management (enable, disable, revoke), and sandboxed execution.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.ecosystem import (
    PluginExecutionRequest,
    PluginExecutionResult,
)
from services.control_plane.dependencies import get_control_plane_manager, require_role
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/plugins", tags=["Plugins & Extensions"])


@router.get("", response_model=list[dict[str, Any]])
async def list_plugins(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
) -> list[dict[str, Any]]:
    """List all registered plugins and their lifecycle states."""
    plugins = manager.plugin_lifecycle.list_plugins()
    # Format for JSON response
    results = []
    for p in plugins:
        if p:
            p_copy = dict(p)
            p_copy["manifest"] = p["manifest"].model_dump()
            if p["previous_manifest"]:
                p_copy["previous_manifest"] = p["previous_manifest"].model_dump()
            p_copy["granted_capabilities"] = [c.value for c in p["granted_capabilities"]]
            p_copy["state"] = p["state"].value
            results.append(p_copy)
    return results


@router.get("/{plugin_id}", response_model=dict[str, Any])
async def get_plugin(
    plugin_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
) -> dict[str, Any]:
    """Retrieve detailed metadata for a specific plugin."""
    p = manager.plugin_lifecycle.get_plugin(plugin_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    p_copy = dict(p)
    p_copy["manifest"] = p["manifest"].model_dump()
    if p["previous_manifest"]:
        p_copy["previous_manifest"] = p["previous_manifest"].model_dump()
    p_copy["granted_capabilities"] = [c.value for c in p["granted_capabilities"]]
    p_copy["state"] = p["state"].value
    return p_copy


@router.post("/{plugin_id}/enable")
async def enable_plugin(
    plugin_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> dict[str, Any]:
    """Enable an installed plugin."""
    try:
        state = manager.plugin_lifecycle.enable_plugin(plugin_id)
        # Update tool specifications in ToolRegistry
        manager.skill_bridge.register_installed_skills()
        return {"plugin_id": plugin_id, "state": state.value, "success": True}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post("/{plugin_id}/disable")
async def disable_plugin(
    plugin_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> dict[str, Any]:
    """Disable an active plugin."""
    try:
        state = manager.plugin_lifecycle.disable_plugin(plugin_id)
        return {"plugin_id": plugin_id, "state": state.value, "success": True}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post("/{plugin_id}/revoke")
async def revoke_plugin(
    plugin_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    reason: str = "Admin revocation",
) -> dict[str, Any]:
    """Permanently revoke a plugin and terminate active instances."""
    try:
        await manager.plugin_lifecycle.emergency_revoke(
            plugin_id, reason=reason, revoked_by=user.username
        )
        return {"plugin_id": plugin_id, "state": "revoked", "success": True}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex


@router.post("/execute", response_model=PluginExecutionResult)
async def execute_plugin_action(
    request: PluginExecutionRequest,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> PluginExecutionResult:
    """Execute a sandboxed action in an enabled plugin."""
    return await manager.plugin_lifecycle.execute_plugin_action(request)
