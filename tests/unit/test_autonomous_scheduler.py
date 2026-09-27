"""Unit tests for AutonomousScheduler, SQLite persistence, and interval calculations."""

from datetime import UTC, datetime, timedelta

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    GoalContract,
    MissedJobPolicy,
    ScheduleType,
    TaskLifecycleState,
)
from services.autonomous.scheduler import AutonomousScheduler


def test_scheduler_one_shot_and_interval() -> None:
    fixed_time = datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC)
    scheduler = AutonomousScheduler(db_path=":memory:", time_fn=lambda: fixed_time)

    goal = GoalContract(objective="Run memory cleanup")
    task_one_shot = AutonomousTaskContract(
        task_id="task_os_1",
        goal=goal,
        schedule_type=ScheduleType.ONE_SHOT,
    )

    scheduler.schedule_task(task_one_shot)
    retrieved = scheduler.get_task("task_os_1")
    assert retrieved is not None
    assert retrieved.state == TaskLifecycleState.SCHEDULED
    assert retrieved.next_run_at == fixed_time

    # Interval task
    task_interval = AutonomousTaskContract(
        task_id="task_int_1",
        goal=goal,
        schedule_type=ScheduleType.INTERVAL,
        schedule_expr="interval:120s",
    )
    scheduler.schedule_task(task_interval)
    retrieved_int = scheduler.get_task("task_int_1")
    assert retrieved_int is not None
    assert retrieved_int.next_run_at == fixed_time + timedelta(seconds=120)


def test_scheduler_due_tasks_and_cancellation() -> None:
    fixed_time = datetime(2026, 9, 27, 12, 0, 0, tzinfo=UTC)
    scheduler = AutonomousScheduler(db_path=":memory:", time_fn=lambda: fixed_time)

    goal = GoalContract(objective="Daily report")
    task = AutonomousTaskContract(
        task_id="task_due_1",
        goal=goal,
        schedule_type=ScheduleType.ONE_SHOT,
    )
    scheduler.schedule_task(task)

    due_list = scheduler.list_due_tasks(now=fixed_time)
    assert len(due_list) == 1
    assert due_list[0].task_id == "task_due_1"

    # Cancel task
    assert scheduler.cancel_task("task_due_1")
    cancelled_task = scheduler.get_task("task_due_1")
    assert cancelled_task is not None
    assert cancelled_task.is_cancelled
    assert cancelled_task.state == TaskLifecycleState.CANCELLED

    # Cancelled tasks are excluded from due list
    due_after_cancel = scheduler.list_due_tasks(now=fixed_time)
    assert len(due_after_cancel) == 0


def test_scheduler_missed_job_skip_policy() -> None:
    sched_time = datetime(2026, 9, 27, 10, 0, 0, tzinfo=UTC)
    mock_now = sched_time

    scheduler = AutonomousScheduler(db_path=":memory:", time_fn=lambda: mock_now)
    goal = GoalContract(objective="Sync telemetry")
    task = AutonomousTaskContract(
        task_id="task_missed_01",
        goal=goal,
        schedule_type=ScheduleType.INTERVAL,
        schedule_expr="interval:60s",
        missed_job_policy=MissedJobPolicy.SKIP,
    )
    scheduler.schedule_task(task)

    # Fast forward time by 2 hours (missed trigger)
    future_time = sched_time + timedelta(hours=2)
    due = scheduler.list_due_tasks(now=future_time)
    assert len(due) == 1

    # Task next_run_at should be rescheduled forward
    updated_task = scheduler.get_task("task_missed_01")
    assert updated_task is not None
    assert updated_task.next_run_at is not None
    assert updated_task.next_run_at > future_time
