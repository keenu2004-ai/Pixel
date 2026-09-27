"""Performance benchmarks for Phase 9 Autonomous Workflows."""

import time
from datetime import UTC, datetime

import pytest

from packages.contracts.autonomous import (
    AutonomousEvent,
    AutonomousTaskContract,
    EventFilter,
    ExecutionBudget,
    GoalContract,
    TaskCheckpoint,
    TaskLifecycleState,
)
from services.autonomous.budget_manager import BudgetManager
from services.autonomous.drift_detector import GoalDriftDetector
from services.autonomous.event_bus import EventBus
from services.autonomous.scheduler import AutonomousScheduler


@pytest.mark.asyncio
async def test_benchmark_event_bus_dispatch_latency() -> None:
    bus = EventBus()

    async def dummy_handler(event: AutonomousEvent) -> None:
        pass

    bus.subscribe("perf_sub", EventFilter(event_type_pattern="benchmark.*"), dummy_handler)

    iterations = 500
    start = time.perf_counter()
    for i in range(iterations):
        evt = AutonomousEvent(
            event_id=f"evt_perf_{i}",
            event_type="benchmark.event",
            source="benchmark",
            correlation_id=f"corr_{i}",
        )
        await bus.publish(evt)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(f"\n[Benchmark] EventBus publish latency: {avg_ms:.3f} ms / event")
    assert avg_ms < 1.0


def test_benchmark_scheduler_task_latency() -> None:
    scheduler = AutonomousScheduler(db_path=":memory:")
    goal = GoalContract(objective="Benchmark task objective")
    task = AutonomousTaskContract(task_id="task_bench", goal=goal)

    iterations = 300
    start = time.perf_counter()
    for i in range(iterations):
        task.task_id = f"task_bench_{i}"
        scheduler.schedule_task(task)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(f"\n[Benchmark] Scheduler schedule latency: {avg_ms:.3f} ms / task")
    assert avg_ms < 2.0


def test_benchmark_goal_drift_detector_latency() -> None:
    detector = GoalDriftDetector()
    goal = GoalContract(
        objective="Analyze source repository files",
        allowed_targets=["src/*", "packages/*"],
        prohibited_actions=["delete", "drop"],
    )

    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        detector.evaluate_drift(
            goal=goal,
            active_plan=[{"description": "Inspect packages folder"}],
            proposed_tools=["read_file"],
            proposed_targets=["packages/core/config.py"],
            current_objective="Analyze source repository files",
        )
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(f"\n[Benchmark] GoalDriftDetector evaluation latency: {avg_ms:.3f} ms / eval")
    assert avg_ms < 0.5


def test_benchmark_budget_manager_record_step_latency() -> None:
    bm = BudgetManager(db_path=":memory:")
    bm.initialize_task_budget("task_bench_b", ExecutionBudget(max_steps=5000))

    iterations = 500
    start = time.perf_counter()
    for _ in range(iterations):
        bm.record_step("task_bench_b", steps=1, tool_calls=1, duration_seconds=0.01)
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(f"\n[Benchmark] BudgetManager record_step latency: {avg_ms:.3f} ms / step")
    assert avg_ms < 1.0


def test_benchmark_checkpoint_hash_and_verify_latency() -> None:
    budget = ExecutionBudget()
    chk = TaskCheckpoint(
        checkpoint_id="chk_perf_01",
        task_id="task_perf_01",
        version=1,
        state=TaskLifecycleState.RUNNING,
        budget=budget,
        active_plan=[{"step": 1, "action": "benchmark"}],
        completed_steps=[],
        execution_evidence=[],
        created_at=datetime.now(UTC),
    )

    iterations = 1000
    start = time.perf_counter()
    for _ in range(iterations):
        chk.checksum = chk.compute_checksum()
        chk.verify_integrity()
    elapsed = time.perf_counter() - start

    avg_ms = (elapsed / iterations) * 1000.0
    print(
        f"\n[Benchmark] TaskCheckpoint SHA-256 compute & verify latency: {avg_ms:.3f} ms / checkpoint"
    )
    assert avg_ms < 0.5
