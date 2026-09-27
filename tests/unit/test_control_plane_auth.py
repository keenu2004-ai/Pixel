"""Unit tests for Control Plane Authentication and RBAC Manager."""

import pytest

from packages.contracts.control_plane import UserRole
from services.control_plane.auth import ControlPlaneAuthManager


def test_auth_manager_initialization() -> None:
    auth = ControlPlaneAuthManager()
    # Check default pre-seeded users
    admin = auth.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None
    assert admin.role == UserRole.ADMIN
    assert admin.username == "admin"

    operator = auth.authenticate("operator", "pixel-operator-2026")
    assert operator is not None
    assert operator.role == UserRole.OPERATOR

    viewer = auth.authenticate("viewer", "pixel-viewer-2026")
    assert viewer is not None
    assert viewer.role == UserRole.READ_ONLY


def test_invalid_credentials() -> None:
    auth = ControlPlaneAuthManager()
    user = auth.authenticate("admin", "wrong-password")
    assert user is None

    unknown = auth.authenticate("non_existent_user", "password")
    assert unknown is None


def test_user_registration() -> None:
    auth = ControlPlaneAuthManager()
    new_user = auth.register_user("new_dev", "dev-password-123", UserRole.OPERATOR)
    assert new_user.username == "new_dev"
    assert new_user.role == UserRole.OPERATOR

    authenticated = auth.authenticate("new_dev", "dev-password-123")
    assert authenticated is not None
    assert authenticated.user_id == new_user.user_id

    # Duplicate registration fails
    with pytest.raises(ValueError, match="already exists"):
        auth.register_user("new_dev", "another_pwd", UserRole.READ_ONLY)


def test_token_creation_and_verification() -> None:
    auth = ControlPlaneAuthManager()
    admin = auth.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None

    token = auth.create_access_token(admin)
    assert isinstance(token, str)
    assert "." in token

    payload = auth.verify_token(token)
    assert payload is not None
    assert payload.sub == admin.user_id
    assert payload.username == "admin"
    assert payload.role == UserRole.ADMIN


def test_token_revocation() -> None:
    auth = ControlPlaneAuthManager()
    admin = auth.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None

    token = auth.create_access_token(admin)
    assert auth.verify_token(token) is not None

    # Revoke
    auth.revoke_token(token)
    assert auth.verify_token(token) is None


def test_token_tampering_defense() -> None:
    auth = ControlPlaneAuthManager()
    admin = auth.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None

    token = auth.create_access_token(admin)
    raw_hex, sig = token.split(".", 1)
    # Modify signature
    tampered_sig = sig[:-4] + "0000"
    tampered_token = f"{raw_hex}.{tampered_sig}"
    assert auth.verify_token(tampered_token) is None


def test_rbac_permission_hierarchy() -> None:
    auth = ControlPlaneAuthManager()
    # READ_ONLY tier
    assert auth.check_permission(UserRole.READ_ONLY, UserRole.READ_ONLY) is True
    assert auth.check_permission(UserRole.READ_ONLY, UserRole.OPERATOR) is False
    assert auth.check_permission(UserRole.READ_ONLY, UserRole.ADMIN) is False

    # OPERATOR tier
    assert auth.check_permission(UserRole.OPERATOR, UserRole.READ_ONLY) is True
    assert auth.check_permission(UserRole.OPERATOR, UserRole.OPERATOR) is True
    assert auth.check_permission(UserRole.OPERATOR, UserRole.ADMIN) is False

    # ADMIN tier
    assert auth.check_permission(UserRole.ADMIN, UserRole.READ_ONLY) is True
    assert auth.check_permission(UserRole.ADMIN, UserRole.OPERATOR) is True
    assert auth.check_permission(UserRole.ADMIN, UserRole.ADMIN) is True
