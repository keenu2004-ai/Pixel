"""Unit tests for Phase 9 autonomous workflow contracts and models."""

from datetime import UTC, datetime

from packages.contracts.autonomous import (
    AutonomousEvent,
    AutonomousTaskContract,
    EventFilter,
    ExecutionBudget,
    GoalContract,
    MissedJobPolicy,
    ScheduleType,
    TaskCheckpoint,
    TaskLifecycleState,
)


def test_execution_budget_bounds() -> None:
    budget = ExecutionBudget(max_steps=5, max_tool_calls=3, max_duration_seconds=10.0)

    # Initial state is within bounds
    exceeded, reason = budget.is_exceeded()
    assert not exceeded
    assert reason is None

    # Exceed steps
    budget.consumed_steps = 5
    exceeded, reason = budget.is_exceeded()
    assert exceeded
    assert "Step budget exceeded" in str(reason)

    # Reset steps and exceed tool calls
    budget.consumed_steps = 2
    budget.consumed_tool_calls = 3
    exceeded, reason = budget.is_exceeded()
    assert exceeded
    assert "Tool call budget exceeded" in str(reason)


def test_task_checkpoint_checksum_integrity() -> None:
    budget = ExecutionBudget()
    checkpoint = TaskCheckpoint(
        checkpoint_id="chk_test_123",
        task_id="task_test_456",
        version=1,
        state=TaskLifecycleState.RUNNING,
        budget=budget,
        active_plan=[{"step_id": "1", "description": "test step"}],
        completed_steps=[],
        execution_evidence=[],
        created_at=datetime.now(UTC),
    )

    # Checksum computation
    checksum = checkpoint.compute_checksum()
    checkpoint.checksum = checksum
    assert checkpoint.verify_integrity()

    # Tampering payload should invalidate checksum
    checkpoint.active_plan.append({"step_id": "2", "description": "unauthorized step"})
    assert not checkpoint.verify_integrity()


def test_event_filter_matching() -> None:
    event = AutonomousEvent(
        event_id="evt_001",
        event_type="device.battery_low",
        source="android_mobile_01",
        correlation_id="corr_123",
        payload={"level": 15, "is_charging": False},
    )

    # Wildcard type filter
    filter_all = EventFilter(event_type_pattern="device.*")
    assert filter_all.matches(event)

    # Exact type filter
    filter_exact = EventFilter(
        event_type_pattern="device.battery_low", source_pattern="android_mobile_01"
    )
    assert filter_exact.matches(event)

    # Payload predicate match
    filter_payload = EventFilter(
        event_type_pattern="device.battery_low",
        payload_predicates={"level": 15, "is_charging": False},
    )
    assert filter_payload.matches(event)

    # Payload predicate mismatch
    filter_mismatch = EventFilter(
        event_type_pattern="device.battery_low",
        payload_predicates={"level": 50},
    )
    assert not filter_mismatch.matches(event)


def test_autonomous_task_contract_serialization() -> None:
    goal = GoalContract(
        objective="Monitor nightly test runs and report failures",
        success_criteria=["Tests executed", "Report generated"],
        allowed_targets=["https://ci.pixel.local/reports"],
        prohibited_actions=["delete_logs", "force_push"],
    )

    task = AutonomousTaskContract(
        task_id="task_nightly_01",
        user_id="user_admin",
        session_id="sess_001",
        goal=goal,
        schedule_type=ScheduleType.INTERVAL,
        schedule_expr="interval:300s",
        missed_job_policy=MissedJobPolicy.EXECUTE_ONCE_NEXT_AVAILABLE,
        allowed_tools=["run_tests", "send_notification"],
    )

    json_data = task.model_dump_json()
    reconstructed = AutonomousTaskContract.model_validate_json(json_data)

    assert reconstructed.task_id == task.task_id
    assert reconstructed.goal.objective == task.goal.objective
    assert reconstructed.schedule_type == ScheduleType.INTERVAL
    assert reconstructed.allowed_tools == ["run_tests", "send_notification"]
