"""System overview and health telemetry API router."""

from typing import Annotated

from fastapi import APIRouter, Depends

from packages.contracts.control_plane import (
    ServiceHealthStatus,
    SystemOverview,
    UserIdentity,
    UserRole,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/overview", tags=["System Overview"])


@router.get("/system", response_model=SystemOverview)
async def get_system_overview(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> SystemOverview:
    """Retrieve authoritative system health, metrics, and active subsystem counts."""
    return await manager.get_system_overview()


@router.get("/health", response_model=list[ServiceHealthStatus])
async def get_subsystem_health(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> list[ServiceHealthStatus]:
    """Retrieve fine-grained health check indicators for individual PIXEL layers."""
    overview = await manager.get_system_overview()
    return overview.services
