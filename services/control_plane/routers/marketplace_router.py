"""
Community Skill Marketplace REST API Router.

Enables searching, viewing security vetting reports, and installing curated community skills.
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.ecosystem import (
    MarketplaceListing,
    PluginCapability,
    SkillInstallRequest,
)
from services.control_plane.dependencies import get_control_plane_manager, require_role
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/marketplace", tags=["Community Marketplace"])


@router.get("/skills", response_model=list[MarketplaceListing])
async def list_marketplace_skills(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    query: Annotated[str | None, Query(description="Search term for name or triggers")] = None,
    capability: Annotated[
        PluginCapability | None, Query(description="Filter by capability")
    ] = None,
    verified_only: Annotated[bool, Query(description="Filter only verified skills")] = False,
) -> list[MarketplaceListing]:
    """List and search available community skills."""
    return manager.marketplace.list_skills(
        query=query,
        capability=capability,
        verified_only=verified_only,
    )


@router.get("/skills/{skill_id}", response_model=MarketplaceListing)
async def get_marketplace_skill(
    skill_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
) -> MarketplaceListing:
    """Retrieve full skill listing, manifest, and security vetting findings."""
    listing = manager.marketplace.get_skill(skill_id)
    if not listing:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' not found in marketplace")
    return listing


@router.post("/install")
async def install_marketplace_skill(
    request: SkillInstallRequest,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Install a verified community skill into the PIXEL runtime."""
    try:
        state = manager.marketplace.install_skill(request, actor=user.username)
        # Register into ToolRegistry
        manager.skill_bridge.register_installed_skills()
        return {"skill_id": request.skill_id, "state": state.value, "success": True}
    except Exception as ex:
        raise HTTPException(status_code=400, detail=str(ex)) from ex
