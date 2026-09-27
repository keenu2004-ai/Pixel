"""Unit tests for HabitRoutineEngine (Habit Observation, Routine Conversion, Proactive Anti-Annoyance Limits)."""

import pytest

from packages.contracts.personalization import (
    PatternStatus,
    ProactiveTriggerType,
)
from services.personalization.habit_routine_engine import HabitRoutineEngine
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def habit_engine() -> HabitRoutineEngine:
    store = UserModelStore(db_path=":memory:")
    return HabitRoutineEngine(
        user_model_store=store,
        default_cooldown_seconds=10,
        max_daily_suggestions=3,
    )


@pytest.mark.asyncio
async def test_habit_observation_remains_observed(habit_engine: HabitRoutineEngine) -> None:
    # 1. Observe action
    habit = await habit_engine.observe_action(
        action_name="open_terminal",
        parameters={"dir": "Pixel"},
        trigger_context="daily_start",
        user_id="u1",
    )
    assert habit.status == PatternStatus.OBSERVED
    assert habit.occurrence_count == 1

    # 2. Observe again
    habit_2 = await habit_engine.observe_action(
        action_name="open_terminal",
        parameters={"dir": "Pixel"},
        trigger_context="daily_start",
        user_id="u1",
    )
    assert habit_2.occurrence_count == 2
    # Still OBSERVED - detection is not permission!
    assert habit_2.status == PatternStatus.OBSERVED


@pytest.mark.asyncio
async def test_approve_habit_to_routine(habit_engine: HabitRoutineEngine) -> None:
    habit = await habit_engine.observe_action(
        action_name="run_daily_backup",
        parameters={},
        trigger_context="evening",
        user_id="u2",
    )

    routine = await habit_engine.approve_habit_to_routine(
        habit_id=habit.habit_id,
        user_id="u2",
        routine_name="Evening Backup Routine",
    )
    assert routine.name == "Evening Backup Routine"
    assert len(routine.steps) == 1
    assert routine.steps[0].tool_or_action == "run_daily_backup"

    habits = await habit_engine.list_habits("u2")
    assert habits[0].status == PatternStatus.USER_APPROVED


@pytest.mark.asyncio
async def test_proactive_assistance_budget_and_cooldown(
    habit_engine: HabitRoutineEngine,
) -> None:
    # 1st suggestion succeeds
    s1 = await habit_engine.generate_proactive_suggestion(
        trigger_type=ProactiveTriggerType.UNFINISHED_TASK,
        headline="Unfinished Task",
        action="resume_task",
        parameters={"task_id": "123"},
        reasoning="You have 1 pending task",
        user_id="u3",
    )
    assert s1 is not None

    # 2nd immediate suggestion is suppressed by cooldown
    s2 = await habit_engine.generate_proactive_suggestion(
        trigger_type=ProactiveTriggerType.KNOWN_DEADLINE,
        headline="Deadline Approaching",
        action="notify",
        parameters={},
        reasoning="Meeting in 15m",
        user_id="u3",
    )
    assert s2 is None


@pytest.mark.asyncio
async def test_proactive_feedback_tracking(habit_engine: HabitRoutineEngine) -> None:
    habit_engine.record_proactive_feedback(user_id="u4", accepted=True)
    budget = habit_engine._get_budget("u4")
    assert budget.accepted_count == 1

    habit_engine.record_proactive_feedback(user_id="u4", accepted=False, dismissed=True)
    assert budget.dismissed_count == 1
    assert budget.cooldown_seconds > 10  # Backoff increased
