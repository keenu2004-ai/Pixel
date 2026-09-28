"""Unit tests for FleetFailureRecoveryEngine."""

from packages.contracts.fleet import (
    FleetCapability,
    FleetDataClassification,
    FleetNodeState,
)
from services.fleet.failure_recovery import FleetFailureRecoveryEngine
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.scheduler import FleetScheduler


def test_node_failure_and_checkpoint_recovery() -> None:
    """Verify recovery when a worker node fails mid-task and task is safely re-assigned or degraded."""
    node_mgr = EdgeNodeManager()
    node_mgr.enroll_node(
        node_id="primary_desktop_core",
        node_name="Central Desktop",
        device_type="DESKTOP",
        capabilities=[FleetCapability.CPU, FleetCapability.GPU],
        is_central_authority=True,
    )
    node_mgr.enroll_node(
        node_id="worker_gpu_node",
        node_name="GPU Server",
        device_type="SERVER",
        capabilities=[FleetCapability.GPU, FleetCapability.LOCAL_LLM],
    )

    scheduler = FleetScheduler(node_manager=node_mgr)
    recovery = FleetFailureRecoveryEngine(node_manager=node_mgr, scheduler=scheduler)

    # Dispatch task to worker_gpu_node
    envelope = scheduler.create_delegation_envelope(
        goal_description="Render high resolution scene",
        capability_required=FleetCapability.GPU,
        source_node_id="primary_desktop_core",
        target_node_id="worker_gpu_node",
        data_classification=FleetDataClassification.SENSITIVE,
    )
    scheduler.grant_lease(envelope.task_id, "worker_gpu_node")

    # Record checkpoint
    scheduler.record_checkpoint(
        task_id=envelope.task_id,
        node_id="worker_gpu_node",
        step_number=5,
        state_payload={"scene_loaded": True, "geometry_baked": True},
    )

    # Worker crashes / goes offline -> recover tasks
    recovered_tasks = recovery.recover_failed_node_tasks("worker_gpu_node")
    assert len(recovered_tasks) == 1
    assert recovered_tasks[0]["task_id"] == envelope.task_id
    assert recovered_tasks[0]["resumed_step"] == 5

    # Malicious detection isolation
    isolated = recovery.detect_and_isolate_malicious_node(
        "worker_gpu_node", violation_type="FORGED_SIGNATURE"
    )
    assert isolated is True
    node = node_mgr.get_node("worker_gpu_node")
    assert node is not None
    assert node.state == FleetNodeState.QUARANTINED
