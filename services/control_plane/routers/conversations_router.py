"""Real-time conversation monitoring API router."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from packages.contracts.control_plane import (
    ConversationSessionView,
    UserIdentity,
    UserRole,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


@router.get("/sessions", response_model=list[ConversationSessionView])
async def list_sessions(
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> list[ConversationSessionView]:
    """List active and recent conversation sessions."""
    return manager.list_conversation_sessions()


@router.get("/sessions/{session_id}", response_model=ConversationSessionView)
async def get_session(
    session_id: str,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> ConversationSessionView:
    """Retrieve detailed turns and telemetry for a specific conversation session."""
    session = manager.get_conversation_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation session '{session_id}' not found.",
        )
    return session
