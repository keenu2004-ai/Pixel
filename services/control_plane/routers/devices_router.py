"""Device Topology & Node Management API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from packages.contracts.control_plane import (
    DeviceActionRequest,
    UserIdentity,
    UserRole,
)
from packages.contracts.orchestration import (
    PairingChallenge,
    PairingConfirmation,
    PairingRequest,
    PairingResponse,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/devices", tags=["Device Topology"])


@router.get("", response_model=list[dict[str, Any]])
async def list_devices(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> list[dict[str, Any]]:
    """List all registered devices, hardware roles, trust states, and real-time presence."""
    return await manager.list_devices()


@router.get("/{device_id}", response_model=dict[str, Any])
async def get_device(
    device_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Retrieve detailed identity, capabilities, and telemetry for a specific device."""
    device = await manager.get_device_detail(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device '{device_id}' not found.",
        )
    return device


@router.post("/pairing/initiate", response_model=PairingChallenge)
async def initiate_pairing(
    req: PairingRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> PairingChallenge:
    """Initiate cryptographic pairing for an unregistered node."""
    try:
        return await manager.initiate_device_pairing(req)
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err)) from err


@router.post("/pairing/confirm", response_model=PairingResponse)
async def confirm_pairing(
    conf: PairingConfirmation,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> PairingResponse:
    """Confirm 6-digit pairing challenge PIN and issue mTLS certificate."""
    return await manager.confirm_device_pairing(conf)


@router.post("/{device_id}/action")
async def execute_device_action(
    device_id: str,
    req: DeviceActionRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Revoke or remove a device node from the trusted topology."""
    success = await manager.execute_device_action(
        device_id=device_id, req=req, actor_id=user.user_id
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to execute action '{req.action}' on device '{device_id}'.",
        )
    return {
        "success": True,
        "device_id": device_id,
        "action": req.action,
        "message": f"Action '{req.action}' executed successfully.",
    }
