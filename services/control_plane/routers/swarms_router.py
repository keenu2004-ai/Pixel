"""Control Plane Swarm and Consensus API Router."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.evolution import (
    AgentHeartbeat,
    AgentProposal,
    AgentVote,
    ConsensusResult,
    SwarmAgentIdentity,
    SwarmSession,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    get_current_user,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/swarms", tags=["Autonomous Swarms"])


@router.post("", response_model=SwarmSession)
async def create_swarm(
    req: dict[str, Any],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> SwarmSession:
    """Creates a new collaborative swarm session."""
    swarm_id = (
        req.get("swarm_id") or f"swarm-{req.get('name', 'session').lower().replace(' ', '-')}"
    )
    name = req.get("name", "Swarm Session")
    max_agents = int(req.get("max_agents", 10))
    budget = req.get("budget")

    return manager.swarm_coordinator.create_swarm(
        swarm_id=swarm_id,
        name=name,
        max_agents=max_agents,
        budget=budget,
    )


@router.get("/{swarm_id}", response_model=SwarmSession)
async def get_swarm(
    swarm_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> SwarmSession:
    """Retrieves an active swarm session."""
    session = manager.swarm_coordinator.get_session(swarm_id)
    if not session:
        raise HTTPException(status_code=404, detail="Swarm session not found")
    return session


@router.post("/{swarm_id}/agents", response_model=dict[str, Any])
async def register_swarm_agent(
    swarm_id: str,
    identity: SwarmAgentIdentity,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> dict[str, Any]:
    """Registers an agent into a swarm session."""
    success = manager.swarm_coordinator.register_agent(swarm_id, identity)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to register agent or swarm at capacity")
    return {"status": "registered", "agent_id": identity.agent_id}


@router.post("/{swarm_id}/heartbeat", response_model=dict[str, Any])
async def record_swarm_heartbeat(
    swarm_id: str,
    heartbeat: AgentHeartbeat,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(get_current_user)],
) -> dict[str, Any]:
    """Processes an agent heartbeat."""
    state = manager.swarm_coordinator.process_heartbeat(swarm_id, heartbeat)
    return {"status": "ok", "agent_state": state.value}


@router.post("/{swarm_id}/proposals", response_model=ConsensusResult)
async def submit_proposal(
    swarm_id: str,
    proposal: AgentProposal,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> ConsensusResult:
    """Submits a proposal to the swarm's consensus engine."""
    proposal.swarm_id = swarm_id
    try:
        return manager.swarm_coordinator.submit_proposal(proposal)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/{swarm_id}/votes", response_model=dict[str, Any])
async def vote_on_proposal(
    swarm_id: str,
    vote: AgentVote,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
) -> dict[str, Any]:
    """Casts a vote on a proposal."""
    success = manager.swarm_coordinator.vote_on_proposal(swarm_id, vote)
    if not success:
        raise HTTPException(status_code=400, detail="Vote rejected or duplicate vote")
    return {"status": "vote_recorded", "proposal_id": vote.proposal_id}


@router.post("/{swarm_id}/proposals/{proposal_id}/finalize", response_model=ConsensusResult)
async def finalize_proposal(
    swarm_id: str,
    proposal_id: str,
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
) -> ConsensusResult:
    """Finalizes proposal consensus tally and evaluates L6/L8 verification."""
    try:
        return manager.swarm_coordinator.finalize_proposal(
            swarm_id=swarm_id,
            proposal_id=proposal_id,
            user_id=user.user_id,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
