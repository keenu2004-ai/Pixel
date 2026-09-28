"""Unit tests for EdgeNodeManager."""

from packages.contracts.fleet import (
    FleetCapability,
    FleetNodeState,
    HardwareProfile,
    NetworkCondition,
    ResourceProfile,
    ThermalState,
)
from services.fleet.node_manager import EdgeNodeManager
from services.orchestration.pki import PKIEngine


def test_node_enrollment_and_lifecycle() -> None:
    """Verify edge node enrollment, heartbeat updates, state transitions, quarantine and revocation."""
    pki = PKIEngine()
    mgr = EdgeNodeManager(pki_engine=pki)

    # 1. Enroll central node
    central_node = mgr.enroll_node(
        node_id="primary_desktop_core",
        node_name="Central Desktop",
        device_type="DESKTOP",
        capabilities=[FleetCapability.CPU, FleetCapability.GPU, FleetCapability.LOCAL_LLM],
        is_central_authority=True,
    )
    assert central_node.state == FleetNodeState.ACTIVE
    assert central_node.identity.is_central_authority is True

    # 2. Enroll edge phone node
    phone_node = mgr.enroll_node(
        node_id="phone_pixel_01",
        node_name="Pixel 9",
        device_type="PHONE",
        capabilities=[
            FleetCapability.MICROPHONE,
            FleetCapability.LOCAL_STT,
            FleetCapability.CAMERA,
        ],
        hardware=HardwareProfile(cpu_cores=8, total_ram_mb=12288),
    )
    assert phone_node.state == FleetNodeState.ACTIVE
    assert mgr.get_node("phone_pixel_01") is not None

    # 3. Heartbeat update
    res = ResourceProfile(
        cpu_usage_percent=45.0,
        ram_free_mb=9288,
        battery_level_percent=88.0,
        is_charging=True,
        thermal_state=ThermalState.NOMINAL,
        network_condition=NetworkCondition.EXCELLENT,
    )
    updated = mgr.record_heartbeat("phone_pixel_01", resources=res)
    assert updated is True
    node = mgr.get_node("phone_pixel_01")
    assert node is not None
    assert node.resources.battery_level_percent == 88.0
    assert node.resources.is_charging is True

    # 4. Quarantine suspicious node
    quarantined = mgr.quarantine_node(
        "phone_pixel_01", reason="Anomalous resource consumption detected"
    )
    assert quarantined is True
    q_node = mgr.get_node("phone_pixel_01")
    assert q_node is not None
    assert q_node.state == FleetNodeState.QUARANTINED
    assert q_node.is_available_for_tasks() is False

    # 5. Revoke node
    revoked = mgr.revoke_node("phone_pixel_01", reason="Cryptographic signature mismatch")
    assert revoked is True
    # Once revoked, get_node returns None
    assert mgr.get_node("phone_pixel_01") is None

    # 6. Heartbeat from revoked node must be rejected
    rejected = mgr.record_heartbeat("phone_pixel_01", resources=res)
    assert rejected is False


def test_heartbeat_timeout_degradation() -> None:
    """Verify that nodes without recent heartbeats are marked offline."""
    mgr = EdgeNodeManager(heartbeat_timeout_seconds=0.001)
    node = mgr.enroll_node(
        node_id="server_node_01",
        node_name="GPU Server",
        device_type="SERVER",
        capabilities=[FleetCapability.GPU, FleetCapability.LOCAL_LLM],
    )
    assert node.state == FleetNodeState.ACTIVE

    import time

    time.sleep(0.01)

    stale = mgr.sweep_stale_heartbeats()
    assert "server_node_01" in stale
    s_node = mgr.get_node("server_node_01")
    assert s_node is not None
    assert s_node.state == FleetNodeState.OFFLINE
