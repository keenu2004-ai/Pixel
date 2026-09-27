"""Hostile Security Red-Team & RBAC Penetration Tests for Phase 10 Control Plane."""

import pytest
from starlette.testclient import TestClient

from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app


@pytest.fixture
def security_test_client() -> tuple[TestClient, ControlPlaneAuthManager, str, str, str]:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    admin = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    operator = auth_mgr.authenticate("operator", "pixel-operator-2026")
    viewer = auth_mgr.authenticate("viewer", "pixel-viewer-2026")

    assert admin and operator and viewer
    return (
        client,
        auth_mgr,
        auth_mgr.create_access_token(admin),
        auth_mgr.create_access_token(operator),
        auth_mgr.create_access_token(viewer),
    )


def test_rbac_privilege_escalation_read_only(
    security_test_client: tuple[TestClient, ControlPlaneAuthManager, str, str, str],
) -> None:
    """Ensure READ_ONLY user cannot create tasks, purge memory, or mutate devices."""
    client, _, _, _, viewer_token = security_test_client
    headers = {"Authorization": f"Bearer {viewer_token}"}

    # 1. Attempt task creation
    res1 = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={"objective": "Escalation task attempt"},
    )
    assert res1.status_code == 403

    # 2. Attempt memory purge
    res2 = client.post(
        "/api/v1/memory/forget",
        headers=headers,
        json={"keyword": "forbidden_topic"},
    )
    assert res2.status_code == 403

    # 3. Attempt device action
    res3 = client.post(
        "/api/v1/devices/primary_desktop_core/action",
        headers=headers,
        json={"action": "REVOKE"},
    )
    assert res3.status_code == 403


def test_rbac_privilege_escalation_operator(
    security_test_client: tuple[TestClient, ControlPlaneAuthManager, str, str, str],
) -> None:
    """Ensure OPERATOR cannot execute ADMIN-only actions like memory purge or device revocation."""
    client, _, _, operator_token, _ = security_test_client
    headers = {"Authorization": f"Bearer {operator_token}"}

    # 1. Attempt memory purge (Requires ADMIN)
    res1 = client.post(
        "/api/v1/memory/forget",
        headers=headers,
        json={"keyword": "confidential"},
    )
    assert res1.status_code == 403

    # 2. Attempt device revocation (Requires ADMIN)
    res2 = client.post(
        "/api/v1/devices/primary_desktop_core/action",
        headers=headers,
        json={"action": "REVOKE"},
    )
    assert res2.status_code == 403


def test_tampered_and_forged_tokens(
    security_test_client: tuple[TestClient, ControlPlaneAuthManager, str, str, str],
) -> None:
    """Verify that forged, malformed, or tampered tokens are rejected with 401."""
    client, _, admin_token, _, _ = security_test_client

    # 1. Fake Bearer Token
    res1 = client.get(
        "/api/v1/overview/system",
        headers={"Authorization": "Bearer fake.jwt.token.12345"},
    )
    assert res1.status_code == 401

    # 2. Altered signature
    raw_hex, sig = admin_token.split(".", 1)
    tampered = f"{raw_hex}.{sig[:-4]}ffff"
    res2 = client.get(
        "/api/v1/overview/system",
        headers={"Authorization": f"Bearer {tampered}"},
    )
    assert res2.status_code == 401


def test_security_headers_enforcement(
    security_test_client: tuple[TestClient, ControlPlaneAuthManager, str, str, str],
) -> None:
    """Verify production security headers are attached to responses."""
    client, _, admin_token, _, _ = security_test_client
    res = client.get(
        "/api/v1/health",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    headers = res.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-xss-protection") == "1; mode=block"
    assert "Content-Security-Policy" in headers or "content-security-policy" in headers
