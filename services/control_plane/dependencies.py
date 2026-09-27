"""FastAPI dependency injection utilities for authentication, RBAC, and runtime manager."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request, status

from packages.contracts.control_plane import UserIdentity, UserRole
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager


def get_auth_manager(request: Request) -> ControlPlaneAuthManager:
    """Retrieve auth manager instance from app state or create default."""
    if hasattr(request.app.state, "auth_manager"):
        return request.app.state.auth_manager  # type: ignore[no-any-return]
    auth_mgr = ControlPlaneAuthManager()
    request.app.state.auth_manager = auth_mgr
    return auth_mgr


def get_control_plane_manager(request: Request) -> ControlPlaneManager:
    """Retrieve runtime control plane manager from app state or create default."""
    if hasattr(request.app.state, "control_plane_manager"):
        return request.app.state.control_plane_manager  # type: ignore[no-any-return]
    mgr = ControlPlaneManager()
    request.app.state.control_plane_manager = mgr
    return mgr


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    auth_manager: Annotated[ControlPlaneAuthManager, Depends(get_auth_manager)] = None,  # type: ignore[assignment]
) -> UserIdentity:
    """Extract and validate bearer token, returning active UserIdentity."""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme. Bearer token required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    token_payload = auth_manager.verify_token(token)
    if not token_payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid, expired, or revoked.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = auth_manager.get_user_by_id(token_payload.sub)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_role(required_role: UserRole) -> Callable[..., Any]:
    """Factory creating dependency to enforce RBAC tier permissions."""

    async def role_checker(
        current_user: Annotated[UserIdentity, Depends(get_current_user)],
        auth_manager: Annotated[ControlPlaneAuthManager, Depends(get_auth_manager)],
    ) -> UserIdentity:
        if not auth_manager.check_permission(current_user.role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires '{required_role.value}' role, user has '{current_user.role.value}'.",
            )
        return current_user

    return role_checker
