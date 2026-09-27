"""Memory inspection and Right-to-Forget API router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from packages.contracts.control_plane import (
    MemoryFactView,
    MemoryPurgeRequest,
    UserIdentity,
    UserRole,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/memory", tags=["Memory & Knowledge"])


class MemorySearchPayload(BaseModel):
    query: str
    limit: int = 10


@router.get("/facts", response_model=list[MemoryFactView])
async def list_facts(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user_id: Annotated[str, Query()] = "default_user",
) -> list[MemoryFactView]:
    """List semantic facts currently stored in persistent memory."""
    return await manager.list_memory_facts(user_id=user_id)


@router.post("/search")
async def search_memory(
    payload: MemorySearchPayload,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Search episodic history and semantic facts."""
    return await manager.search_memory(
        query=payload.query, user_id=user.user_id, limit=payload.limit
    )


@router.post("/forget")
async def forget_memory(
    req: MemoryPurgeRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Purge facts and episodic records matching a topic under Right to Forget."""
    deleted_count = await manager.forget_memory(keyword=req.keyword, user_id=req.user_id)
    return {
        "success": True,
        "keyword": req.keyword,
        "deleted_records_count": deleted_count,
    }
