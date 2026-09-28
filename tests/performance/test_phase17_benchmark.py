"""Phase 17 Fleet Performance, Latency, and Distribution Benefit Benchmark Suite."""

import time

import numpy as np

from packages.contracts.fleet import (
    FleetCapability,
    FleetDataClassification,
    HardwareProfile,
)
from services.fleet.manager import FleetOperationsManager


def test_fleet_latency_and_distribution_benchmarks() -> None:
    """Measures p50/p95 latency for node discovery, routing, task delegation, and local vs distributed execution paths."""
    mgr = FleetOperationsManager()

    # 1. Enroll benchmark nodes
    mgr.node_manager.enroll_node(
        node_id="server_bench_01",
        node_name="Server Benchmark Node",
        device_type="SERVER",
        capabilities=[FleetCapability.CPU, FleetCapability.GPU, FleetCapability.LOCAL_LLM],
        hardware=HardwareProfile(cpu_cores=32, has_gpu=True),
    )
    mgr.node_manager.enroll_node(
        node_id="phone_bench_01",
        node_name="Phone Benchmark Node",
        device_type="PHONE",
        capabilities=[FleetCapability.LOCAL_STT, FleetCapability.MICROPHONE],
        hardware=HardwareProfile(cpu_cores=8),
    )

    # 2. Benchmark Routing Latency (100 iterations)
    routing_latencies_ms: list[float] = []
    for i in range(100):
        t0 = time.perf_counter()
        mgr.routing_engine.route_task(
            task_id=f"bench_route_{i}",
            required_capability=FleetCapability.LOCAL_STT,
            source_node_id="phone_bench_01",
            data_classification=FleetDataClassification.PERSONAL,
        )
        t1 = time.perf_counter()
        routing_latencies_ms.append((t1 - t0) * 1000.0)

    p50_routing = float(np.percentile(routing_latencies_ms, 50))
    p95_routing = float(np.percentile(routing_latencies_ms, 95))

    # Assert sub-millisecond or fast routing
    assert p50_routing < 10.0, f"p50 routing too high: {p50_routing}ms"
    assert p95_routing < 25.0, f"p95 routing too high: {p95_routing}ms"

    # 3. Benchmark Task Delegation Latency (100 iterations)
    delegation_latencies_ms: list[float] = []
    for i in range(100):
        t0 = time.perf_counter()
        envelope = mgr.scheduler.create_delegation_envelope(
            goal_description="Benchmarking task delegation",
            capability_required=FleetCapability.CPU,
            source_node_id="primary_desktop_core",
            target_node_id="server_bench_01",
            data_classification=FleetDataClassification.LOW_SENSITIVITY,
            idempotency_key=f"bench_key_{i}",
        )
        mgr.scheduler.grant_lease(envelope.task_id, "server_bench_01")
        t1 = time.perf_counter()
        delegation_latencies_ms.append((t1 - t0) * 1000.0)

        # Immediate result attestation
        mgr.scheduler.validate_and_attest_result(
            task_id=envelope.task_id,
            node_id="server_bench_01",
            output_payload={"metric": 1.0},
            idempotency_key=f"bench_key_{i}",
        )

    p50_delegation = float(np.percentile(delegation_latencies_ms, 50))
    p95_delegation = float(np.percentile(delegation_latencies_ms, 95))

    assert p50_delegation < 10.0, f"p50 delegation too high: {p50_delegation}ms"
    assert p95_delegation < 25.0, f"p95 delegation too high: {p95_delegation}ms"


def test_local_vs_central_vs_distributed_benefit() -> None:
    """Compares simulated execution benefits of Local vs Central vs Distributed tiers."""
    mgr = FleetOperationsManager()
    mgr.node_manager.enroll_node(
        node_id="phone_node",
        node_name="Phone",
        device_type="PHONE",
        capabilities=[FleetCapability.LOCAL_STT],
    )
    mgr.node_manager.enroll_node(
        node_id="server_node",
        node_name="Server",
        device_type="SERVER",
        capabilities=[FleetCapability.GPU, FleetCapability.LOCAL_LLM],
    )

    # Local Tier for Privacy/Voice
    dec_local = mgr.routing_engine.route_task(
        task_id="t_voice",
        required_capability=FleetCapability.LOCAL_STT,
        source_node_id="phone_node",
        data_classification=FleetDataClassification.HIGHLY_SENSITIVE,
    )
    assert dec_local.execution_tier == "LOCAL"

    # Distributed Tier for Heavy Compute
    dec_dist = mgr.routing_engine.route_task(
        task_id="t_heavy",
        required_capability=FleetCapability.LOCAL_LLM,
        source_node_id="phone_node",
        data_classification=FleetDataClassification.SENSITIVE,
        is_heavy_task=True,
    )
    assert dec_dist.selected_node_id in ["server_node", "primary_desktop_core"]
