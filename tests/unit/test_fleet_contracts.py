"""Unit tests for Phase 17 Fleet contracts."""

from datetime import UTC, datetime, timedelta

from packages.contracts.fleet import (
    AutonomousFleetMission,
    DelegatedTaskEnvelope,
    DistributedTaskCheckpoint,
    EdgeNode,
    EdgeNodeIdentity,
    FleetCapability,
    FleetDataClassification,
    FleetKillSwitchDomain,
    FleetModelSpec,
    FleetNodeState,
    HardwareProfile,
    ModelDistributionPackage,
    NetworkCondition,
    ResourceProfile,
    RoutingDecision,
    TaskLease,
    ThermalState,
    WorkerResultAttestation,
)


def test_fleet_contracts_instantiation() -> None:
    """Verify that all fleet contract models instantiate and validate accurately."""
    identity = EdgeNodeIdentity(
        node_id="phone_pixel9_01",
        node_name="Pixel 9 Pro",
        device_type="PHONE",
        public_key_fingerprint="abc123fingerprint",
        certificate_serial="cert_001",
        is_central_authority=False,
    )
    assert identity.node_id == "phone_pixel9_01"

    hw = HardwareProfile(
        cpu_cores=8,
        has_gpu=False,
        has_npu=True,
        total_ram_mb=12288,
    )
    assert hw.has_npu is True

    res = ResourceProfile(
        cpu_usage_percent=25.0,
        ram_free_mb=8192,
        battery_level_percent=85.0,
        is_charging=False,
        thermal_state=ThermalState.NOMINAL,
        network_condition=NetworkCondition.EXCELLENT,
    )
    assert res.battery_level_percent == 85.0

    node = EdgeNode(
        identity=identity,
        state=FleetNodeState.ACTIVE,
        hardware=hw,
        resources=res,
        capabilities=[
            FleetCapability.MICROPHONE,
            FleetCapability.LOCAL_STT,
            FleetCapability.CAMERA,
        ],
    )
    assert node.state == FleetNodeState.ACTIVE
    assert FleetCapability.LOCAL_STT in node.capabilities

    model_spec = FleetModelSpec(
        model_id="whisper-tiny-edge",
        model_name="Whisper Tiny Local",
        version="1.0.0",
        architecture="whisper",
        size_mb=75,
        ram_requirement_mb=256,
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        supported_capabilities=[FleetCapability.LOCAL_STT],
    )
    assert model_spec.model_id == "whisper-tiny-edge"

    package = ModelDistributionPackage(
        model_spec=model_spec,
        target_node_id="phone_pixel9_01",
        download_url="https://models.pixel.internal/whisper.bin",
        sha256_checksum="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        signed_by_authority="auth_signature",
    )
    assert package.target_node_id == "phone_pixel9_01"

    decision = RoutingDecision(
        task_id="task_001",
        selected_node_id="phone_pixel9_01",
        target_capability=FleetCapability.LOCAL_STT,
        data_classification=FleetDataClassification.PERSONAL,
        execution_tier="LOCAL",
        reason="Local STT on phone minimizes privacy exposure and network latency.",
        estimated_latency_ms=15.0,
        confidence=0.98,
    )
    assert decision.execution_tier == "LOCAL"

    now = datetime.now(UTC)
    lease = TaskLease(
        task_id="task_12345",
        node_id="phone_pixel9_01",
        expires_at=now + timedelta(seconds=30),
        ttl_seconds=30,
    )
    assert lease.is_expired() is False

    envelope = DelegatedTaskEnvelope(
        task_id="task_12345",
        goal_description="Transcribe user voice stream",
        capability_required=FleetCapability.LOCAL_STT,
        data_classification=FleetDataClassification.PERSONAL,
        source_node_id="primary_desktop_core",
        target_node_id="phone_pixel9_01",
    )
    assert envelope.task_id == "task_12345"

    checkpoint = DistributedTaskCheckpoint(
        task_id="task_12345",
        node_id="phone_pixel9_01",
        step_number=1,
        state_payload={"step": "audio_captured"},
    )
    assert checkpoint.step_number == 1

    attestation = WorkerResultAttestation(
        task_id="task_12345",
        node_id="phone_pixel9_01",
        success=True,
        output_payload={"transcript": "Turn on the living room lights"},
    )
    assert attestation.success is True

    mission = AutonomousFleetMission(
        mission_id="mission_001",
        title="Distributed Swarm Mission",
        goal="Capture screen on PC, analyze on Server, respond on Phone",
        max_delegation_depth=3,
    )
    assert mission.max_delegation_depth == 3
    assert FleetKillSwitchDomain.ALL_EDGE_EXECUTION == "ALL_EDGE_EXECUTION"
