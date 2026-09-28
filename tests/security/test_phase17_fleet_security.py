"""Phase 17 Fleet Security and Adversarial Attack Suite.

Hostile security verification against:
- Node spoofing & forged credentials
- Expired task lease exploitation
- Execution attempts by revoked/quarantined nodes
- Malicious delegation loops / swarm escalation beyond bounded depth
- Highly sensitive data leakage across network boundaries
- Fleet kill switch enforcement
"""

from datetime import UTC, datetime, timedelta

import pytest

from packages.contracts.fleet import (
    DelegatedTaskEnvelope,
    FleetCapability,
    FleetDataClassification,
    FleetKillSwitchDomain,
    TaskLease,
)
from services.fleet.manager import FleetOperationsManager


def test_adversarial_revoked_node_execution_defense() -> None:
    """Attack 1: Revoked node attempts to receive delegated tasks or submit results."""
    mgr = FleetOperationsManager()

    # Enroll edge phone
    mgr.node_manager.enroll_node(
        node_id="compromised_phone",
        node_name="Compromised Device",
        device_type="PHONE",
        capabilities=[FleetCapability.MICROPHONE, FleetCapability.LOCAL_STT],
    )

    # Immediately revoke
    mgr.node_manager.revoke_node("compromised_phone", reason="Key compromised")
    assert mgr.node_manager.get_node("compromised_phone") is None

    # Re-enrollment attempt must be blocked
    with pytest.raises(PermissionError, match="permanently revoked"):
        mgr.node_manager.enroll_node(
            node_id="compromised_phone",
            node_name="Compromised Device",
            device_type="PHONE",
        )


def test_adversarial_stale_lease_rejection() -> None:
    """Attack 2: Worker node attempts to submit results after task lease has expired."""
    mgr = FleetOperationsManager()

    mgr.node_manager.enroll_node(
        node_id="slow_worker_01",
        node_name="Slow Worker",
        device_type="PHONE",
        capabilities=[FleetCapability.LOCAL_STT],
    )

    envelope = mgr.scheduler.create_delegation_envelope(
        goal_description="Transcribe long recording",
        capability_required=FleetCapability.LOCAL_STT,
        source_node_id="primary_desktop_core",
        target_node_id="slow_worker_01",
        data_classification=FleetDataClassification.PERSONAL,
    )

    # Grant expired lease
    now = datetime.now(UTC)
    mgr.scheduler._leases[envelope.task_id] = TaskLease(
        task_id=envelope.task_id,
        node_id="slow_worker_01",
        granted_at=now - timedelta(seconds=40),
        expires_at=now - timedelta(seconds=10),
        ttl_seconds=30,
        is_active=True,
    )

    with pytest.raises(PermissionError, match="lacks active execution lease"):
        mgr.scheduler.validate_and_attest_result(
            task_id=envelope.task_id,
            node_id="slow_worker_01",
            output_payload={"text": "Late result"},
        )


def test_adversarial_delegation_escalation_depth_defense() -> None:
    """Attack 3: Swarm escalation attempt (A -> B -> C -> D) exceeding max bounded depth."""
    mgr = FleetOperationsManager()

    mgr.mission_governor.create_mission(
        title="Escalation Test",
        goal="Coordinated visual analysis",
    )

    # Delegation depth 1, 2 ok
    envelope_ok = DelegatedTaskEnvelope(
        source_node_id="A",
        target_node_id="B",
        goal_description="Step 1",
        capability_required=FleetCapability.CPU,
        current_delegation_depth=1,
    )
    valid, err = mgr.mission_governor.validate_delegation(envelope_ok)
    assert valid is True
    assert err is None

    # Delegation depth 3 (max depth is 3 -> rejected)
    envelope_overflow = DelegatedTaskEnvelope(
        source_node_id="C",
        target_node_id="D",
        goal_description="Step 4 overflow",
        capability_required=FleetCapability.CPU,
        current_delegation_depth=3,
    )
    valid, err = mgr.mission_governor.validate_delegation(envelope_overflow)
    assert valid is False
    assert "Maximum delegation depth" in (err or "")


def test_adversarial_highly_sensitive_privacy_leak_defense() -> None:
    """Attack 4: Highly sensitive payload (passwords, OTPs) attempting remote delegation."""
    mgr = FleetOperationsManager()

    mgr.node_manager.enroll_node(
        node_id="phone_local_node",
        node_name="Pixel Device",
        device_type="PHONE",
        capabilities=[FleetCapability.LOCAL_STT, FleetCapability.MICROPHONE],
    )

    # Route highly sensitive request from phone
    decision = mgr.routing_engine.route_task(
        task_id="task_bank_otp",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_local_node",
        data_classification=FleetDataClassification.HIGHLY_SENSITIVE,
    )

    # Must be forced to LOCAL tier on origin node, NEVER remote
    assert decision.execution_tier == "LOCAL"
    assert decision.selected_node_id == "phone_local_node"


def test_adversarial_fleet_kill_switch_enforcement() -> None:
    """Attack 5: Verifying emergency fleet kill switches."""
    mgr = FleetOperationsManager()

    # Activate ALL_EDGE_EXECUTION kill switch
    mgr.kill_switches.activate_kill_switch(
        FleetKillSwitchDomain.ALL_EDGE_EXECUTION, reason="Emergency Security Lockdown"
    )
    assert mgr.kill_switches.is_blocked(FleetKillSwitchDomain.ALL_EDGE_EXECUTION) is True
    assert mgr.kill_switches.is_blocked(FleetKillSwitchDomain.REMOTE_INFERENCE) is True
    assert mgr.kill_switches.is_blocked(FleetKillSwitchDomain.MEMORY_SYNC) is True

    # Deactivate kill switch
    mgr.kill_switches.deactivate_kill_switch(FleetKillSwitchDomain.ALL_EDGE_EXECUTION)
    assert mgr.kill_switches.is_blocked(FleetKillSwitchDomain.ALL_EDGE_EXECUTION) is False
