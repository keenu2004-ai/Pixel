"""PIXEL — Control Plane Personalization & Adaptive Assistant Router.

Exposes REST APIs for:
1. User Model & Preference Profiles
2. Preference Explainability & Reversibility
3. Habits & Routine Approval
4. Personal Goals & Continuity
5. Personal Vocabulary & Entity Resolution
6. Cross-Device Personal Context Sync
7. Right-to-Forget Cascading Purge
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.personalization import (
    EntityType,
    PersonalContextSyncDelta,
    PersonalEntity,
    PersonalGoal,
    UserRoutine,
)
from packages.contracts.user_model import UserModel
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/personalization", tags=["Personalization & Adaptive Assistant"])


class SetPreferenceRequest(BaseModel):
    key: str
    value: Any
    user_id: str = "default_user"


class ApproveHabitRequest(BaseModel):
    habit_id: str
    routine_name: str | None = None
    user_id: str = "default_user"


class CreateGoalRequest(BaseModel):
    title: str
    description: str = ""
    priority: int = 1
    active_project_path: str | None = None
    tags: list[str] = []
    user_id: str = "default_user"


class RegisterEntityRequest(BaseModel):
    canonical_name: str
    entity_type: EntityType
    aliases: list[str] = []
    context_metadata: dict[str, Any] = {}
    user_id: str = "default_user"


class PersonalPurgeRequest(BaseModel):
    keyword: str | None = None
    user_id: str = "default_user"


@router.get("/model", response_model=UserModel)
async def get_user_model(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user_id: Annotated[str, Query()] = "default_user",
) -> UserModel:
    """Retrieves full UserModel aggregate for user."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.get_user_model(user_id=user_id)
    return UserModel(user_id=user_id)


@router.put("/preferences")
async def update_preference(
    req: SetPreferenceRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Sets explicit preference."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        rec = await manager.personalization_manager.set_preference(
            key=req.key, value=req.value, user_id=req.user_id
        )
        return {"success": True, "record": rec.model_dump()}
    return {"success": False, "error": "PersonalizationManager not configured"}


@router.get("/explain")
async def explain_preference(
    key: Annotated[str, Query()],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user_id: Annotated[str, Query()] = "default_user",
) -> dict[str, Any]:
    """Explains why a preference is active with provenance and confidence."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.explain(key=key, user_id=user_id)
    return {"error": "PersonalizationManager not configured"}


@router.post("/goals", response_model=PersonalGoal)
async def create_goal(
    req: CreateGoalRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> PersonalGoal:
    """Creates or updates a personal goal."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.register_goal(
            title=req.title,
            description=req.description,
            priority=req.priority,
            active_project_path=req.active_project_path,
            tags=req.tags,
            user_id=req.user_id,
        )
    raise HTTPException(status_code=500, detail="PersonalizationManager not available")


@router.post("/habits/approve", response_model=UserRoutine)
async def approve_habit(
    req: ApproveHabitRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> UserRoutine:
    """Authorizes an observed habit pattern, converting it to an active routine."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.approve_habit_to_routine(
            habit_id=req.habit_id, user_id=req.user_id, routine_name=req.routine_name
        )
    raise HTTPException(status_code=500, detail="PersonalizationManager not available")


@router.post("/entities", response_model=PersonalEntity)
async def register_entity(
    req: RegisterEntityRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> PersonalEntity:
    """Registers an entity alias or project mapping."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.register_entity(
            canonical_name=req.canonical_name,
            entity_type=req.entity_type,
            aliases=req.aliases,
            context_metadata=req.context_metadata,
            user_id=req.user_id,
        )
    raise HTTPException(status_code=500, detail="PersonalizationManager not available")


@router.post("/corrections/undo")
async def undo_last_correction(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user_id: Annotated[str, Query()] = "default_user",
) -> dict[str, Any]:
    """Rolls back the most recent user correction."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        event = await manager.personalization_manager.correction_learner.undo_last_correction(
            user_id=user_id
        )
        return {"success": True, "event": event.model_dump() if event else None}
    return {"success": False, "error": "PersonalizationManager not configured"}


@router.post("/sync/delta", response_model=PersonalContextSyncDelta)
async def create_sync_delta(
    origin_device_id: Annotated[str, Query()],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user_id: Annotated[str, Query()] = "default_user",
) -> PersonalContextSyncDelta:
    """Generates cross-device sync delta."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        return await manager.personalization_manager.create_sync_delta(
            origin_device_id=origin_device_id, user_id=user_id
        )
    raise HTTPException(status_code=500, detail="PersonalizationManager not available")


@router.post("/purge")
async def purge_personal_memory(
    req: PersonalPurgeRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Right to Forget cascade purge across personal models and knowledge stores."""
    if hasattr(manager, "personalization_manager") and manager.personalization_manager:
        purged = await manager.personalization_manager.purge_user_memory(
            user_id=req.user_id, keyword=req.keyword
        )
        return {"success": True, "purged_records_count": purged}
    return {"success": False, "error": "PersonalizationManager not configured"}
