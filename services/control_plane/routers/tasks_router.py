"""Autonomous tasks control API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    TaskCheckpoint,
    TaskLifecycleState,
)
from packages.contracts.control_plane import (
    CreateTaskRequest,
    TaskActionRequest,
    TaskActionResponse,
    TaskSummary,
    UserIdentity,
    UserRole,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/tasks", tags=["Autonomous Tasks"])


@router.get("", response_model=list[TaskSummary])
async def list_tasks(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    state: Annotated[TaskLifecycleState | None, Query()] = None,
) -> list[TaskSummary]:
    """List autonomous tasks with optional lifecycle state filter."""
    return await manager.list_tasks(state=state)


@router.post("", response_model=AutonomousTaskContract)
async def create_task(
    req: CreateTaskRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> AutonomousTaskContract:
    """Create and submit a new autonomous task."""
    return await manager.create_task(req, user_id=user.user_id)


@router.get("/{task_id}", response_model=AutonomousTaskContract)
async def get_task(
    task_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> AutonomousTaskContract:
    """Get full specification and budget status of a task."""
    task = await manager.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return task


@router.post("/{task_id}/action", response_model=TaskActionResponse)
async def execute_task_action(
    task_id: str,
    req: TaskActionRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> TaskActionResponse:
    """Execute lifecycle action (PAUSE, RESUME, CANCEL, APPROVE, REJECT, TRIGGER_NOW) on a task."""
    return await manager.execute_task_action(task_id=task_id, req=req, actor_id=user.user_id)


@router.get("/{task_id}/checkpoints", response_model=list[TaskCheckpoint])
async def get_task_checkpoints(
    task_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> list[TaskCheckpoint]:
    """Retrieve cryptographic checkpoint history for a task."""
    task = await manager.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{task_id}' not found.",
        )
    return manager.get_task_checkpoints(task_id)
