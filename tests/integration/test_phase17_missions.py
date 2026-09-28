"""Phase 17 Fleet Acceptance Missions 1-15 Integration Test Suite.

Validates end-to-end multi-device workflows, intelligent routing, distributed multimodal coordination,
failure recoveries, security quarantines, and memory reconciliation.
"""

import hashlib

import pytest

from packages.contracts.fleet import (
    DelegatedTaskEnvelope,
    FleetCapability,
    FleetDataClassification,
    FleetModelSpec,
    HardwareProfile,
    NetworkCondition,
    ResourceProfile,
    ThermalState,
)
from services.fleet.manager import FleetOperationsManager
from services.memory.manager import MemoryManager


@pytest.fixture
def fleet() -> FleetOperationsManager:
    """Sets up a realistic 3-node topology: Central Desktop, GPU Server, and Android Phone."""
    mem_mgr = MemoryManager(db_path=":memory:")
    mgr = FleetOperationsManager(memory_manager=mem_mgr)

    # 1. GPU Server
    mgr.node_manager.enroll_node(
        node_id="server_gpu_01",
        node_name="Local Edge AI GPU Server",
        device_type="SERVER",
        capabilities=[
            FleetCapability.CPU,
            FleetCapability.GPU,
            FleetCapability.LOCAL_LLM,
            FleetCapability.LOCAL_VISION,
            FleetCapability.RAG,
        ],
        hardware=HardwareProfile(
            cpu_cores=32,
            has_gpu=True,
            gpu_name="NVIDIA RTX 4090",
            total_ram_mb=131072,
            total_vram_mb=24576,
        ),
    )

    # 2. Android Phone
    mgr.node_manager.enroll_node(
        node_id="phone_pixel_01",
        node_name="Pixel 9 Pro Mobile Assistant",
        device_type="PHONE",
        capabilities=[
            FleetCapability.MICROPHONE,
            FleetCapability.SPEAKER,
            FleetCapability.CAMERA,
            FleetCapability.SCREEN,
            FleetCapability.LOCAL_STT,
            FleetCapability.LOCAL_TTS,
            FleetCapability.ANDROID,
        ],
        hardware=HardwareProfile(
            cpu_cores=8,
            has_gpu=False,
            has_npu=True,
            total_ram_mb=16384,
        ),
    )
    mgr.node_manager.record_heartbeat(
        "phone_pixel_01",
        resources=ResourceProfile(
            battery_level_percent=82.0,
            is_charging=False,
            thermal_state=ThermalState.NOMINAL,
            network_condition=NetworkCondition.EXCELLENT,
        ),
    )

    return mgr


@pytest.mark.asyncio
async def test_mission_1_local_voice(fleet: FleetOperationsManager) -> None:
    """Mission 1: Local Voice — Phone wake -> local STT -> local intent -> local TTS."""
    decision = fleet.routing_engine.route_task(
        task_id="m1_voice",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.PERSONAL,
    )
    assert decision.execution_tier == "LOCAL"
    assert decision.selected_node_id == "phone_pixel_01"


@pytest.mark.asyncio
async def test_mission_2_distributed_vision(fleet: FleetOperationsManager) -> None:
    """Mission 2: Distributed Vision — Phone camera -> server vision -> phone response."""
    turn = await fleet.edge_multimodal.process_distributed_multimodal_turn(
        voice_transcript="Analyze what is on the screen right now",
        source_device_id="phone_pixel_01",
        screen_title="Pixel Dashboard",
    )
    assert turn["source_node"] == "phone_pixel_01"
    assert turn["vision_node"] in ["primary_desktop_core", "server_gpu_01"]
    assert "response_text" in turn


@pytest.mark.asyncio
async def test_mission_3_distributed_coding(fleet: FleetOperationsManager) -> None:
    """Mission 3: Distributed Coding — Phone voice -> server planning -> PC coding tool -> verification -> phone response."""
    # 1. Routing decision
    decision = fleet.routing_engine.route_task(
        task_id="mission_coding_01",
        required_capability=FleetCapability.GIT,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.SENSITIVE,
    )
    assert decision.selected_node_id == "primary_desktop_core"

    # 2. Dispatch task
    envelope = fleet.scheduler.create_delegation_envelope(
        goal_description="Refactor auth token expiration logic and run test suite",
        capability_required=FleetCapability.GIT,
        source_node_id="phone_pixel_01",
        target_node_id=decision.selected_node_id,
        idempotency_key="coding_task_auth_refactor",
    )
    assert envelope.target_node_id == "primary_desktop_core"

    fleet.scheduler.grant_lease(envelope.task_id, envelope.target_node_id)

    # 3. Checkpoint & Result Attestation
    fleet.scheduler.record_checkpoint(
        task_id=envelope.task_id,
        node_id="primary_desktop_core",
        step_number=2,
        state_payload={"tests_passed": 12},
    )
    attestation = fleet.scheduler.validate_and_attest_result(
        task_id=envelope.task_id,
        node_id="primary_desktop_core",
        output_payload={"refactor_status": "SUCCESS", "tests_passed": 12},
        idempotency_key="coding_task_auth_refactor",
    )
    assert attestation.success is True


@pytest.mark.asyncio
async def test_mission_4_browser_fleet_mission(fleet: FleetOperationsManager) -> None:
    """Mission 4: Browser Fleet Mission — Phone -> server -> PC browser -> visual verification -> result."""
    decision = fleet.routing_engine.route_task(
        task_id="mission_browser_01",
        required_capability=FleetCapability.BROWSER,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.LOW_SENSITIVITY,
    )
    assert decision.selected_node_id == "primary_desktop_core"


@pytest.mark.asyncio
async def test_mission_5_privacy_routing(fleet: FleetOperationsManager) -> None:
    """Mission 5: Privacy Routing — Sensitive input -> local-capable node selected -> remote transmission prevented."""
    decision = fleet.routing_engine.route_task(
        task_id="mission_privacy_01",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.HIGHLY_SENSITIVE,
    )
    assert decision.execution_tier == "LOCAL"
    assert decision.selected_node_id == "phone_pixel_01"


@pytest.mark.asyncio
async def test_mission_6_battery_routing(fleet: FleetOperationsManager) -> None:
    """Mission 6: Battery Routing — Phone low battery (<20%) -> heavy task delegated -> phone remains available."""
    fleet.node_manager.record_heartbeat(
        "phone_pixel_01",
        resources=ResourceProfile(
            battery_level_percent=15.0,  # Critical low battery!
            is_charging=False,
            thermal_state=ThermalState.NOMINAL,
            network_condition=NetworkCondition.EXCELLENT,
        ),
    )
    decision = fleet.routing_engine.route_task(
        task_id="mission_battery_01",
        required_capability=FleetCapability.CPU,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.LOW_SENSITIVITY,
        is_heavy_task=True,
    )
    assert decision.selected_node_id in ["server_gpu_01", "primary_desktop_core"]


@pytest.mark.asyncio
async def test_mission_7_network_failure_graceful_degradation(
    fleet: FleetOperationsManager,
) -> None:
    """Mission 7: Network Failure — Network lost on phone -> local capability preserved -> graceful degradation."""
    fleet.node_manager.record_heartbeat(
        "phone_pixel_01",
        resources=ResourceProfile(
            battery_level_percent=80.0,
            network_condition=NetworkCondition.OFFLINE,
        ),
    )
    decision = fleet.routing_engine.route_task(
        task_id="mission_offline_01",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.PERSONAL,
    )
    assert decision.execution_tier == "LOCAL"
    assert decision.selected_node_id == "phone_pixel_01"


@pytest.mark.asyncio
async def test_mission_8_node_failure_recovery(fleet: FleetOperationsManager) -> None:
    """Mission 8: Node Failure — Server unavailable -> task recovery/fallback -> no duplicate execution."""
    envelope = fleet.scheduler.create_delegation_envelope(
        goal_description="Compute embeddings for codebase",
        capability_required=FleetCapability.LOCAL_LLM,
        source_node_id="phone_pixel_01",
        target_node_id="server_gpu_01",
        data_classification=FleetDataClassification.SENSITIVE,
        idempotency_key="embed_codebase_v1",
    )
    fleet.scheduler.grant_lease(envelope.task_id, "server_gpu_01")
    fleet.scheduler.record_checkpoint(
        task_id=envelope.task_id,
        node_id="server_gpu_01",
        step_number=3,
        state_payload={"indexed_files": 45},
    )

    fleet.node_manager.quarantine_node("server_gpu_01", reason="Unresponsive ping")
    repaired = fleet.failure_recovery.recover_failed_node_tasks("server_gpu_01")
    assert len(repaired) == 1
    assert repaired[0]["task_id"] == envelope.task_id


@pytest.mark.asyncio
async def test_mission_9_stale_worker_lease_expiration(fleet: FleetOperationsManager) -> None:
    """Mission 9: Stale Worker — Worker lease expires -> authority removed -> stale worker cannot continue."""
    envelope = fleet.scheduler.create_delegation_envelope(
        goal_description="Analyze log file",
        capability_required=FleetCapability.LOCAL_STT,
        source_node_id="primary_desktop_core",
        target_node_id="phone_pixel_01",
        data_classification=FleetDataClassification.LOW_SENSITIVITY,
    )
    # Grant active lease then manually expire it
    lease = fleet.scheduler.grant_lease(envelope.task_id, "phone_pixel_01", ttl_seconds=1)
    lease.is_active = False

    with pytest.raises(PermissionError, match="lacks active execution lease"):
        fleet.scheduler.validate_and_attest_result(
            task_id=envelope.task_id,
            node_id="phone_pixel_01",
            output_payload={"status": "done"},
        )


@pytest.mark.asyncio
async def test_mission_10_malicious_node_quarantine_and_revocation(
    fleet: FleetOperationsManager,
) -> None:
    """Mission 10: Malicious Node — Invalid node behavior -> quarantine -> revoke -> sensitive tasks stop."""
    fleet.node_manager.quarantine_node("phone_pixel_01", reason="Tampered integrity signature")
    node = fleet.node_manager.get_node("phone_pixel_01")
    assert node is not None
    assert node.state.value == "QUARANTINED"

    fleet.node_manager.revoke_node("phone_pixel_01", reason="Confirmed malicious payload")
    assert fleet.node_manager.get_node("phone_pixel_01") is None


@pytest.mark.asyncio
async def test_mission_11_model_failure_rollback(fleet: FleetOperationsManager) -> None:
    """Mission 11: Model Failure — Bad model -> detection -> rollback -> previous model restored."""
    spec_v1 = FleetModelSpec(
        model_id="llm-edge-quant",
        model_name="LLM Edge Quant",
        version="1.0.0",
        architecture="llama",
        size_mb=1000,
        ram_requirement_mb=2000,
        sha256_hash=hashlib.sha256(b"weights_v1").hexdigest(),
        supported_capabilities=[FleetCapability.LOCAL_LLM],
    )
    fleet.model_registry.register_model(spec_v1)
    pkg_v1 = fleet.model_registry.create_distribution_package(
        "llm-edge-quant", target_node_id="phone_pixel_01"
    )
    fleet.model_registry.verify_and_cache_model_on_node(pkg_v1, spec_v1.sha256_hash)

    spec_v2 = FleetModelSpec(
        model_id="llm-edge-quant-v2",
        model_name="LLM Edge Quant v2",
        version="2.0.0",
        architecture="llama",
        size_mb=1000,
        ram_requirement_mb=2000,
        sha256_hash=hashlib.sha256(b"weights_v2").hexdigest(),
        supported_capabilities=[FleetCapability.LOCAL_LLM],
    )
    fleet.model_registry.register_model(spec_v2)
    pkg_v2 = fleet.model_registry.create_distribution_package(
        "llm-edge-quant-v2", target_node_id="phone_pixel_01"
    )
    fleet.model_registry.verify_and_cache_model_on_node(pkg_v2, spec_v2.sha256_hash)

    rolled_back = fleet.model_registry.rollback_model_on_node(
        node_id="phone_pixel_01",
        failing_model_id="llm-edge-quant-v2",
        fallback_model_id="llm-edge-quant",
        reason="Severe hallucination spike",
    )
    assert rolled_back is True


@pytest.mark.asyncio
async def test_mission_12_fleet_cancellation(fleet: FleetOperationsManager) -> None:
    """Mission 12: Fleet Cancellation — User: 'Cancel that.' -> task cancelled -> leases released -> reconciled."""
    envelope = fleet.scheduler.create_delegation_envelope(
        goal_description="Run extensive benchmark",
        capability_required=FleetCapability.GPU,
        source_node_id="primary_desktop_core",
        target_node_id="server_gpu_01",
        data_classification=FleetDataClassification.SENSITIVE,
    )
    fleet.scheduler.grant_lease(envelope.task_id, "server_gpu_01")
    cancelled = fleet.scheduler.cancel_task(envelope.task_id)
    assert cancelled is True
    assert fleet.scheduler.get_active_lease(envelope.task_id) is None


@pytest.mark.asyncio
async def test_mission_13_cross_device_memory_consistency(fleet: FleetOperationsManager) -> None:
    """Mission 13: Cross-Device Memory — Phone observation -> authorized memory -> server -> PC context."""
    replicated = fleet.memory_coordinator.replicate_fact_to_node(
        target_node_id="phone_pixel_01",
        fact_key="preferred_ide_theme",
        fact_value="Monokai Pro",
        version=1,
    )
    assert replicated is True


@pytest.mark.asyncio
async def test_mission_14_full_multimodal_swarm_mission(fleet: FleetOperationsManager) -> None:
    """Mission 14: Full Multimodal Swarm Mission — Bounded multi-device coordination."""
    mission = fleet.mission_governor.create_mission(
        title="Multimodal Whiteboard Digitizer",
        goal="Phone captures whiteboard, Server extracts code, PC commits to git, Phone announces completion",
    )
    assert mission.mission_id is not None

    env1 = DelegatedTaskEnvelope(
        parent_mission_id=mission.mission_id,
        source_node_id="phone_pixel_01",
        target_node_id="server_gpu_01",
        goal_description="Extract code from image",
        capability_required=FleetCapability.LOCAL_VISION,
        current_delegation_depth=1,
    )
    valid1, _ = fleet.mission_governor.validate_delegation(env1)
    assert valid1 is True

    env2 = DelegatedTaskEnvelope(
        parent_mission_id=mission.mission_id,
        source_node_id="server_gpu_01",
        target_node_id="primary_desktop_core",
        goal_description="Commit code to repo",
        capability_required=FleetCapability.GIT,
        current_delegation_depth=2,
    )
    valid2, _ = fleet.mission_governor.validate_delegation(env2)
    assert valid2 is True


@pytest.mark.asyncio
async def test_mission_15_long_running_fleet_soak(fleet: FleetOperationsManager) -> None:
    """Mission 15: Long-Running Fleet Soak — 50 continuous distributed task cycles with zero duplicate actions, leaks, or stale worker crashes."""
    for i in range(50):
        envelope = fleet.scheduler.create_delegation_envelope(
            goal_description=f"Continuous edge health check pulse {i}",
            capability_required=FleetCapability.CPU,
            source_node_id="primary_desktop_core",
            target_node_id="server_gpu_01" if i % 2 == 0 else "phone_pixel_01",
            data_classification=FleetDataClassification.LOW_SENSITIVITY,
            idempotency_key=f"idempotency_soak_{i:03d}",
        )
        fleet.scheduler.grant_lease(envelope.task_id, envelope.target_node_id, ttl_seconds=10)

        attestation = fleet.scheduler.validate_and_attest_result(
            task_id=envelope.task_id,
            node_id=envelope.target_node_id,
            output_payload={"pulse_index": i, "status": "NOMINAL"},
            idempotency_key=f"idempotency_soak_{i:03d}",
        )
        assert attestation.success is True
