"""End-to-End Integration tests for PIXEL Production Control Plane.

Verifies full-stack interoperability across Voice Gateway, Task Governor,
Scheduler, Memory Store, Device Registry, and Control Plane API.
"""

import pytest
from starlette.testclient import TestClient

from packages.contracts.events import VoiceState
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.autonomous.budget_manager import BudgetManager
from services.autonomous.drift_detector import GoalDriftDetector
from services.autonomous.engine import AutonomousWorkflowEngine
from services.autonomous.governor import TaskGovernor
from services.autonomous.notifications import TaskNotificationManager
from services.autonomous.scheduler import AutonomousScheduler
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app
from services.memory.manager import MemoryManager
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager


@pytest.fixture
def integrated_runtime() -> tuple[TestClient, ControlPlaneManager, ControlPlaneAuthManager, str]:
    auth_mgr = ControlPlaneAuthManager()
    pki = PKIEngine()
    device_registry = DeviceRegistry(pki_engine=pki)
    presence_mgr = PresenceManager()
    memory_mgr = MemoryManager(db_path=":memory:")
    scheduler = AutonomousScheduler(db_path=":memory:")
    budget_mgr = BudgetManager(db_path=":memory:")
    drift_det = GoalDriftDetector()
    gov = TaskGovernor(max_concurrent_tasks=5)
    notif = TaskNotificationManager()
    gate = AgentPolicyGate()

    tool_reg = ToolRegistry()
    engine = AutonomousWorkflowEngine(
        scheduler=scheduler,
        budget_manager=budget_mgr,
        drift_detector=drift_det,
        governor=gov,
        notification_manager=notif,
        policy_gate=gate,
        tool_registry=tool_reg,
    )

    manager = ControlPlaneManager(
        device_registry=device_registry,
        presence_manager=presence_mgr,
        scheduler=scheduler,
        autonomous_engine=engine,
        budget_manager=budget_mgr,
        drift_detector=drift_det,
        memory_manager=memory_mgr,
        policy_gate=gate,
        tool_registry=tool_reg,
    )

    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    admin = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None
    admin_token = auth_mgr.create_access_token(admin)

    return client, manager, auth_mgr, admin_token


@pytest.mark.asyncio
async def test_full_stack_lifecycle_flow(
    integrated_runtime: tuple[TestClient, ControlPlaneManager, ControlPlaneAuthManager, str],
) -> None:
    client, manager, _, token = integrated_runtime
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Check Initial System Overview
    res = client.get("/api/v1/overview/system", headers=headers)
    assert res.status_code == 200
    overview = res.json()
    assert overview["is_online"] is True
    assert overview["active_devices_count"] == 1  # Primary desktop

    # 2. Simulate Conversation Activity
    manager.record_session_turn(
        session_id="integration_sess_10",
        user_id="user_vaibhav",
        device_id="primary_desktop_core",
        voice_state=VoiceState.THINKING,
        user_query="Schedule an autonomous code audit task",
        assistant_response="Scheduling code audit with 10 steps max budget.",
    )

    sess_res = client.get("/api/v1/conversations/sessions", headers=headers)
    assert sess_res.status_code == 200
    sessions = sess_res.json()
    assert len(sessions) == 1
    assert sessions[0]["session_id"] == "integration_sess_10"

    # 3. Create Autonomous Task via Control Plane API
    task_res = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "objective": "Autonomous security audit of microservices",
            "schedule_type": "ONE_SHOT",
            "max_steps": 15,
            "max_tool_calls": 5,
        },
    )
    assert task_res.status_code == 200
    task_data = task_res.json()
    task_id = task_data["task_id"]

    # 4. Trigger Execution Slice
    action_res = client.post(
        f"/api/v1/tasks/{task_id}/action",
        headers=headers,
        json={"action": "TRIGGER_NOW"},
    )
    assert action_res.status_code == 200
    assert action_res.json()["success"] is True

    # 5. Check Checkpoints
    chk_res = client.get(f"/api/v1/tasks/{task_id}/checkpoints", headers=headers)
    assert chk_res.status_code == 200
    checkpoints = chk_res.json()
    assert len(checkpoints) >= 1
    assert "checksum" in checkpoints[0]

    # 6. Pair New Satellite Device Node
    sat_pub = "-----BEGIN PUBLIC KEY-----\nsatellite_pubkey_test_12345\n-----END PUBLIC KEY-----"

    pair_init_res = client.post(
        "/api/v1/devices/pairing/initiate",
        headers=headers,
        json={
            "device_id": "satellite_living_room",
            "device_name": "Living Room Satellite Mic",
            "device_role": "SATELLITE_MIC_SPEAKER",
            "public_key_pem": sat_pub,
            "capabilities": ["MICROPHONE", "SPEAKER", "WAKE_WORD"],
        },
    )
    assert pair_init_res.status_code == 200
    challenge = pair_init_res.json()
    pin = challenge["pin_code"]

    # Confirm Pairing
    confirm_res = client.post(
        "/api/v1/devices/pairing/confirm",
        headers=headers,
        json={
            "challenge_id": challenge["challenge_id"],
            "device_id": "satellite_living_room",
            "pin_code": pin,
            "user_confirmed": True,
            "auth_signature": "sig_valid_test",
        },
    )
    assert confirm_res.status_code == 200
    assert confirm_res.json()["success"] is True

    # 7. Verify Topology Reflects Both Devices
    devices_res = client.get("/api/v1/devices", headers=headers)
    assert devices_res.status_code == 200
    devices = devices_res.json()
    assert len(devices) == 2

    # 8. Revoke Satellite Device
    revoke_res = client.post(
        "/api/v1/devices/satellite_living_room/action",
        headers=headers,
        json={"action": "REVOKE", "reason": "Decommissioned node"},
    )
    assert revoke_res.status_code == 200
    assert revoke_res.json()["success"] is True
