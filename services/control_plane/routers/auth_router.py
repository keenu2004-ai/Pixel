"""Authentication API router for PIXEL Control Plane."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status

from packages.contracts.control_plane import LoginRequest, LoginResponse, UserIdentity
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.dependencies import get_auth_manager, get_current_user

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    auth_manager: Annotated[ControlPlaneAuthManager, Depends(get_auth_manager)],
) -> LoginResponse:
    """Authenticate user with username and password."""
    user = auth_manager.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or inactive user account",
        )

    token = auth_manager.create_access_token(user)
    return LoginResponse(
        access_token=token,
        token_type="Bearer",
        expires_in_seconds=auth_manager.token_lifetime_seconds,
        user=user,
    )


@router.post("/logout")
async def logout(
    authorization: Annotated[str | None, Header()] = None,
    auth_manager: Annotated[ControlPlaneAuthManager, Depends(get_auth_manager)] = None,  # type: ignore[assignment]
    current_user: Annotated[UserIdentity, Depends(get_current_user)] = None,  # type: ignore[assignment]
) -> dict[str, str]:
    """Revoke active bearer token."""
    if authorization and " " in authorization:
        token = authorization.split(" ")[1]
        auth_manager.revoke_token(token)
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserIdentity)
async def get_my_profile(
    current_user: Annotated[UserIdentity, Depends(get_current_user)],
) -> UserIdentity:
    """Retrieve identity and RBAC role of current authenticated user."""
    return current_user
