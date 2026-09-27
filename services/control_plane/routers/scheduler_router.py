"""Persistent Scheduler management API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from packages.contracts.autonomous import AutonomousTaskContract
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

router = APIRouter(prefix="/api/v1/scheduler", tags=["Scheduler"])


@router.get("/jobs", response_model=list[TaskSummary])
async def list_jobs(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> list[TaskSummary]:
    """List all scheduled jobs in the persistent scheduler."""
    return await manager.list_tasks()


@router.post("/jobs", response_model=AutonomousTaskContract)
async def create_job(
    req: CreateTaskRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> AutonomousTaskContract:
    """Schedule a new recurring or one-shot job."""
    return await manager.create_task(req, user_id=user.user_id)


@router.get("/jobs/{task_id}", response_model=AutonomousTaskContract)
async def get_job(
    task_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> AutonomousTaskContract:
    """Get schedule and recurrence metadata of a job."""
    task = await manager.get_task_detail(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scheduled job '{task_id}' not found.",
        )
    return task


@router.post("/jobs/{task_id}/action", response_model=TaskActionResponse)
async def execute_job_action(
    task_id: str,
    req: TaskActionRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> TaskActionResponse:
    """Pause, resume, or cancel a scheduled job."""
    return await manager.execute_task_action(task_id=task_id, req=req, actor_id=user.user_id)
