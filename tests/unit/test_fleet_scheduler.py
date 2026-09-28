"""Unit tests for FleetScheduler."""

from packages.contracts.fleet import (
    FleetCapability,
    FleetDataClassification,
)
from services.fleet.node_manager import EdgeNodeManager
from services.fleet.scheduler import FleetScheduler


def test_fleet_scheduler_lifecycle() -> None:
    """Verify task delegation envelope creation, exclusive lease acquisition, checkpoints, cancellation, and idempotency."""
    node_mgr = EdgeNodeManager()
    node_mgr.enroll_node(
        node_id="primary_desktop_core",
        node_name="Central Desktop",
        device_type="DESKTOP",
        capabilities=[FleetCapability.CPU, FleetCapability.GPU],
        is_central_authority=True,
    )
    node_mgr.enroll_node(
        node_id="phone_pixel_01",
        node_name="Pixel Phone",
        device_type="PHONE",
        capabilities=[FleetCapability.MICROPHONE, FleetCapability.LOCAL_STT],
    )

    scheduler = FleetScheduler(node_manager=node_mgr)

    # 1. Dispatch Delegated Task
    envelope = scheduler.create_delegation_envelope(
        goal_description="Transcribe audio stream",
        capability_required=FleetCapability.LOCAL_STT,
        source_node_id="primary_desktop_core",
        target_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.PERSONAL,
        idempotency_key="stt_run_001",
    )
    assert envelope.capability_required == FleetCapability.LOCAL_STT
    assert envelope.target_node_id == "phone_pixel_01"

    # Grant lease
    lease = scheduler.grant_lease(
        task_id=envelope.task_id, node_id="phone_pixel_01", ttl_seconds=15
    )
    assert lease.node_id == "phone_pixel_01"
    assert scheduler.get_active_lease(envelope.task_id) is not None

    # 2. Checkpoint submission
    ckpt = scheduler.record_checkpoint(
        task_id=envelope.task_id,
        node_id="phone_pixel_01",
        step_number=1,
        state_payload={"chunk": 1},
    )
    assert ckpt is not None
    assert ckpt.step_number == 1
    assert scheduler.get_latest_checkpoint(envelope.task_id) is not None

    # 3. Result Attestation & Verification with Idempotency
    attestation = scheduler.validate_and_attest_result(
        task_id=envelope.task_id,
        node_id="phone_pixel_01",
        output_payload={"text": "Open the garage door"},
        idempotency_key="stt_run_001",
    )
    assert attestation.success is True

    # 4. Duplicate execution with same idempotency key returns cached attestation
    cached_attestation = scheduler.validate_and_attest_result(
        task_id="task_stt_dup",
        node_id="phone_pixel_01",
        output_payload={"text": "Should not execute"},
        idempotency_key="stt_run_001",
    )
    assert cached_attestation.task_id == envelope.task_id

    # 5. Cancellation test
    envelope_to_cancel = scheduler.create_delegation_envelope(
        goal_description="Task to be cancelled",
        capability_required=FleetCapability.CPU,
        source_node_id="primary_desktop_core",
        target_node_id="phone_pixel_01",
    )
    scheduler.grant_lease(envelope_to_cancel.task_id, "phone_pixel_01")
    cancelled = scheduler.cancel_task(envelope_to_cancel.task_id)
    assert cancelled is True
    assert scheduler.get_active_lease(envelope_to_cancel.task_id) is None
