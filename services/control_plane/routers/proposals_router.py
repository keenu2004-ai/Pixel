"""Control Plane Change Proposals and Self-Healing API Router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.evolution import (
    ChangeProposal,
    ChangeProposalState,
    RemediationProposal,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    get_current_user,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/proposals", tags=["Change Proposals & Self-Healing"])


@router.get("", response_model=list[ChangeProposal])
async def list_proposals(
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
    state: ChangeProposalState | None = None,
) -> list[ChangeProposal]:
    """Lists change proposals with optional state filter."""
    return manager.proposal_manager.list_proposals(state=state)


@router.get("/{proposal_id}", response_model=ChangeProposal)
async def get_proposal(
    proposal_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> ChangeProposal:
    """Retrieves a change proposal by ID."""
    prop = manager.proposal_manager.get_proposal(proposal_id)
    if not prop:
        raise HTTPException(status_code=404, detail="Change proposal not found")
    return prop


@router.post("/execute-remediation", response_model=ChangeProposal)
async def execute_remediation(
    remediation: RemediationProposal,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> ChangeProposal:
    """Processes a remediation proposal through the self-healing orchestrator."""
    if not manager.evolution_governor.can_execute_remediation():
        raise HTTPException(
            status_code=403,
            detail="Autonomous remediation is blocked by governor policy or tripped kill switch",
        )
    return manager.self_healing.process_remediation(
        proposal=remediation,
        actor_id=user.user_id,
    )


@router.post("/{proposal_id}/rollback", response_model=dict[str, Any])
async def rollback_proposal(
    proposal_id: str,
    req: dict[str, str],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> dict[str, Any]:
    """Manually triggers rollback of a change proposal."""
    reason = req.get("reason", "Manual operator rollback")
    success = manager.self_healing.trigger_rollback(proposal_id=proposal_id, reason=reason)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot rollback proposal or not found")
    return {"status": "rolled_back", "proposal_id": proposal_id}
