"""Audit log inspection API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.security import AuditRecord
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/audit", tags=["Audit & Security"])


@router.get("/logs", response_model=list[AuditRecord])
async def query_audit_logs(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    actor_id: Annotated[str | None, Query()] = None,
    tool_name: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[AuditRecord]:
    """Query immutable policy decisions and execution audit trail."""
    return manager.get_audit_logs(actor_id=actor_id, tool_name=tool_name, limit=limit)
