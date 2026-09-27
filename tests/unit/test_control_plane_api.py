"""Unit tests for Control Plane REST API endpoints."""

import pytest
from starlette.testclient import TestClient

from packages.contracts.events import VoiceState
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app


@pytest.fixture
def test_setup() -> tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str]:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    # Get admin token
    admin_user = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    assert admin_user is not None
    admin_token = auth_mgr.create_access_token(admin_user)

    # Get viewer token
    viewer_user = auth_mgr.authenticate("viewer", "pixel-viewer-2026")
    assert viewer_user is not None
    viewer_token = auth_mgr.create_access_token(viewer_user)

    return client, auth_mgr, manager, admin_token, viewer_token


def test_auth_login_endpoint(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, _, _ = test_setup
    res = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "pixel-admin-secure-2026"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "access_token" in data
    assert data["user"]["role"] == "ADMIN"


def test_auth_me_endpoint(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, _ = test_setup
    res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"


def test_system_overview_endpoint(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, _ = test_setup
    res = client.get(
        "/api/v1/overview/system",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_online"] is True
    assert "services" in data
    assert len(data["services"]) > 0


def test_conversations_endpoint(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, manager, admin_token, _ = test_setup
    # Record a test session turn
    manager.record_session_turn(
        session_id="test_sess_01",
        user_id="usr_001",
        device_id="desktop_core",
        voice_state=VoiceState.SPEAKING,
        user_query="Hello Pixel",
        assistant_response="Hello! How can I assist you?",
    )

    res = client.get(
        "/api/v1/conversations/sessions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) >= 1
    assert any(s["session_id"] == "test_sess_01" for s in sessions)


def test_tasks_crud_and_actions(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, viewer_token = test_setup
    # 1. Create Task (Operator/Admin)
    create_res = client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "objective": "Test autonomous task creation",
            "schedule_type": "ONE_SHOT",
            "max_steps": 10,
        },
    )
    assert create_res.status_code == 200
    task_data = create_res.json()
    task_id = task_data["task_id"]
    assert task_id.startswith("task_")

    # 2. List Tasks
    list_res = client.get(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert list_res.status_code == 200
    tasks = list_res.json()
    assert any(t["task_id"] == task_id for t in tasks)

    # 3. Pause Task Action
    pause_res = client.post(
        f"/api/v1/tasks/{task_id}/action",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "PAUSE"},
    )
    assert pause_res.status_code == 200
    assert pause_res.json()["new_state"] == "PAUSED"

    # 4. Resume Task Action
    resume_res = client.post(
        f"/api/v1/tasks/{task_id}/action",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action": "RESUME"},
    )
    assert resume_res.status_code == 200
    assert resume_res.json()["new_state"] == "SCHEDULED"

    # 5. Checkpoints
    chk_res = client.get(
        f"/api/v1/tasks/{task_id}/checkpoints",
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert chk_res.status_code == 200
    checkpoints = chk_res.json()
    assert len(checkpoints) >= 1


def test_memory_facts_and_search(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, _ = test_setup
    res = client.get(
        "/api/v1/memory/facts",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)

    search_res = client.post(
        "/api/v1/memory/search",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"query": "assistant settings", "limit": 5},
    )
    assert search_res.status_code == 200
    assert "facts" in search_res.json()


def test_devices_topology_endpoint(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, _ = test_setup
    res = client.get(
        "/api/v1/devices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    devices = res.json()
    assert len(devices) >= 1
    assert devices[0]["identity"]["device_id"] == "primary_desktop_core"


def test_rbac_forbidden_action(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, _, viewer_token = test_setup
    # Viewer (READ_ONLY) attempting to create a task -> 403 Forbidden
    res = client.post(
        "/api/v1/tasks",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"objective": "Unauthorized task creation"},
    )
    assert res.status_code == 403
    assert "Forbidden" in res.json()["detail"]


def test_audit_logs_query(
    test_setup: tuple[TestClient, ControlPlaneAuthManager, ControlPlaneManager, str, str],
) -> None:
    client, _, _, admin_token, _ = test_setup
    res = client.get(
        "/api/v1/audit/logs",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res.status_code == 200
    assert isinstance(res.json(), list)
