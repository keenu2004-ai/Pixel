"""Control Plane Emergency Kill Switches API Router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.evolution import KillSwitchDomain, KillSwitchStatus
from services.control_plane.dependencies import (
    get_control_plane_manager,
    get_current_user,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/killswitches", tags=["Emergency Kill Switches"])


@router.get("", response_model=dict[str, KillSwitchStatus])
async def list_kill_switches(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> dict[str, KillSwitchStatus]:
    """Retrieves all emergency kill switch statuses."""
    return manager.kill_switches.list_all_statuses()


@router.post("/{domain}/trip", response_model=KillSwitchStatus)
async def trip_kill_switch(
    domain: KillSwitchDomain,
    req: dict[str, str],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> KillSwitchStatus:
    """Trips an emergency kill switch to immediately halt operations in that domain."""
    reason = req.get("reason", "Operator emergency intervention")
    return manager.kill_switches.trip_switch(
        domain=domain,
        tripped_by=user.user_id,
        reason=reason,
    )


@router.post("/{domain}/reset", response_model=KillSwitchStatus)
async def reset_kill_switch(
    domain: KillSwitchDomain,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> KillSwitchStatus:
    """Resets an emergency kill switch back to normal operations."""
    return manager.kill_switches.reset_switch(
        domain=domain,
        reset_by=user.user_id,
    )
