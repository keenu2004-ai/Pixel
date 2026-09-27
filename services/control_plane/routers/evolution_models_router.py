"""Control Plane Evolved Models and Differential Privacy API Router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.evolution import (
    DifferentialPrivacyBudget,
    ModelPromotionDecision,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    get_current_user,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/evolution/models", tags=["Evolved Models & Privacy"])


@router.get("", response_model=list[dict[str, Any]])
async def list_evolved_models(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    """Lists all registered evolved models."""
    return manager.model_registry.list_models()


@router.get("/dp-budget", response_model=DifferentialPrivacyBudget)
async def get_privacy_budget(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> DifferentialPrivacyBudget:
    """Retrieves current differential privacy budget state."""
    return manager.dp_accountant.budget


@router.post("/lineage/revoke-user", response_model=dict[str, Any])
async def revoke_user_training_consent(
    req: dict[str, str],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Revokes user consent for all training interactions (Right-to-be-Forgotten)."""
    target_user_id = req.get("user_id") or user.user_id
    revoked_count = manager.lineage_tracker.revoke_user_consent(target_user_id)
    return {"status": "revoked", "user_id": target_user_id, "records_revoked": revoked_count}


@router.post("/{model_id}/promote-canary", response_model=ModelPromotionDecision)
async def promote_model_canary(
    model_id: str,
    req: dict[str, Any],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> ModelPromotionDecision:
    """Promotes candidate model to canary rollout."""
    if not manager.evolution_governor.can_promote_model():
        raise HTTPException(status_code=403, detail="Model promotion is blocked by kill switch")

    canary_percent = int(req.get("canary_percent", 10))
    try:
        return manager.model_registry.promote_to_canary(
            candidate_model_id=model_id,
            canary_percent=canary_percent,
            promoted_by=user.user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{model_id}/rollback", response_model=dict[str, Any])
async def rollback_model(
    model_id: str,
    req: dict[str, str],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Rolls back an active or canary evolved model."""
    reason = req.get("reason", "Operator model rollback")
    success = manager.model_registry.rollback_model(model_id, reason=reason)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot rollback model")
    return {"status": "rolled_back", "model_id": model_id}
