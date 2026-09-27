"""Integration tests for Multi-Device Orchestration & Satellite Topology.

Simulates end-to-end distributed system topology with PC nodes, Android mobile
clients, and room satellite microphones coordinating under PIXEL Core authority.
"""

from datetime import UTC, datetime
from typing import Any

import pytest

from packages.contracts.agent import ApprovalCard
from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceTrustState,
)
from packages.contracts.tools import RiskClass
from services.orchestration.arbitration import WakeArbiter
from services.orchestration.handoff import HandoffManager
from services.orchestration.mock_nodes import (
    MockAndroidNode,
    MockPCNode,
    MockSatelliteNode,
)
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager


@pytest.fixture
def topology_env() -> dict[str, Any]:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)
    presence = PresenceManager(heartbeat_timeout_seconds=10.0)
    arbiter = WakeArbiter()
    handoff = HandoffManager(registry=registry, presence=presence)

    pc = MockPCNode(device_id="desktop-pc-01", device_name="Dev Workstation")
    phone = MockAndroidNode(device_id="android-phone-01", device_name="Pixel 8")
    satellite_living = MockSatelliteNode(device_id="sat-living-room", device_name="Living Room Satellite")
    satellite_kitchen = MockSatelliteNode(device_id="sat-kitchen", device_name="Kitchen Satellite")

    # Pair and register all devices into registry
    for node in [pc, phone, satellite_living, satellite_kitchen]:
        req = node.create_pairing_request()
        challenge = registry.initiate_pairing(req)
        conf = node.answer_pairing_challenge(challenge)
        resp = registry.complete_pairing(conf)
        node.install_certificate(resp)
        node.send_heartbeat(presence)

    return {
        "pki": pki,
        "registry": registry,
        "presence": presence,
        "arbiter": arbiter,
        "handoff": handoff,
        "pc": pc,
        "phone": phone,
        "sat_living": satellite_living,
        "sat_kitchen": satellite_kitchen,
    }


def test_topology_all_nodes_paired_and_authenticated(topology_env: dict[str, Any]) -> None:
    registry: DeviceRegistry = topology_env["registry"]
    presence: PresenceManager = topology_env["presence"]
    pc: MockPCNode = topology_env["pc"]
    phone: MockAndroidNode = topology_env["phone"]

    # Verify trust in registry
    pc_dev = registry.get_device(pc.device_id)
    assert pc_dev is not None
    assert pc_dev.trust_state == DeviceTrustState.TRUSTED

    phone_dev = registry.get_device(phone.device_id)
    assert phone_dev is not None
    assert phone_dev.trust_state == DeviceTrustState.TRUSTED

    # Verify mTLS authentication succeeds
    assert pc.certificate_pem is not None
    ok, _ = registry.authenticate_device_connection(pc.device_id, pc.certificate_pem)
    assert ok is True

    # Verify all 4 nodes are online
    online = presence.get_online_devices()
    assert len(online) == 4


def test_multi_satellite_wake_arbitration_flow(topology_env: dict[str, Any]) -> None:
    arbiter: WakeArbiter = topology_env["arbiter"]
    sat_living: MockSatelliteNode = topology_env["sat_living"]
    sat_kitchen: MockSatelliteNode = topology_env["sat_kitchen"]
    phone: MockAndroidNode = topology_env["phone"]

    # User speaks "Hey Pixel" in the living room
    # Living room satellite has high confidence (0.98) and close proximity (1.0m)
    # Kitchen satellite has medium confidence (0.80) and 5.0m distance
    # Phone in pocket has 0.75 confidence and 3.0m distance
    utterance_id = "utterance-living-room-001"

    sat_kitchen.emit_wake_candidate(
        arbiter=arbiter,
        wake_event_id=utterance_id,
        timestamp_ms=1005,
        confidence=0.80,
        snr_db=12.0,
        estimated_distance_m=5.0,
    )

    phone.emit_wake_candidate(
        arbiter=arbiter,
        wake_event_id=utterance_id,
        timestamp_ms=1010,
        confidence=0.75,
        snr_db=10.0,
        estimated_distance_m=3.0,
    )

    res = sat_living.emit_wake_candidate(
        arbiter=arbiter,
        wake_event_id=utterance_id,
        timestamp_ms=1000,
        confidence=0.98,
        snr_db=24.0,
        estimated_distance_m=1.0,
    )

    # Living room satellite is unambiguously elected
    assert res.winner_device_id == sat_living.device_id
    assert sat_kitchen.device_id in res.suppressed_device_ids
    assert phone.device_id in res.suppressed_device_ids
    assert arbiter.get_active_audio_owner() == sat_living.device_id


def test_cross_device_task_handoff_with_approval_preservation(topology_env: dict[str, Any]) -> None:
    handoff: HandoffManager = topology_env["handoff"]
    pc: MockPCNode = topology_env["pc"]
    phone: MockAndroidNode = topology_env["phone"]

    # Phone initiated a high-impact coding task requiring confirmation
    approval = ApprovalCard(
        approval_id="appr-888",
        task_id="task-code-refactor",
        session_id="session-123",
        user_id="user-primary",
        tool_name="apply_patch",
        arguments={"file": "core.py", "lines": 42},
        arguments_hash="hash-42",
        risk_class=RiskClass.HIGH_IMPACT.value,
        reason="Modifying core business logic",
        confirmation_token="hmac-token-secret-123",
        created_at=datetime.now(UTC),
    )

    plan_steps = [
        {"step_id": 1, "action": "read_file", "status": "COMPLETED"},
        {"step_id": 2, "action": "apply_patch", "status": "PENDING"},
    ]

    # Migrate task from Mobile to PC Workstation (which has CODE_EXECUTION and DESKTOP_CONTROL)
    task_payload = handoff.initiate_task_handoff(
        source_device_id=phone.device_id,
        target_device_id=pc.device_id,
        task_id="task-code-refactor",
        current_version=1,
        plan_steps=plan_steps,
        current_step_index=1,
        pending_approval=approval.model_dump(),
        required_capability=DeviceCapability.CODE_EXECUTION,
    )

    assert task_payload.task_version == 2
    assert task_payload.pending_approval is not None
    assert task_payload.pending_approval["tool_name"] == "apply_patch"
    assert task_payload.pending_approval["confirmation_token"] == "hmac-token-secret-123"

    # PC Workstation completes handoff
    complete_ok = handoff.complete_task_handoff(
        task_id="task-code-refactor",
        target_device_id=pc.device_id,
        lease_token=task_payload.concurrency_lease_token,
    )
    assert complete_ok is True

