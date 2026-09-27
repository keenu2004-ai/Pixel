"""Unit tests for GoalTracker (Goal Continuity, Multi-day Task Progression)."""

import pytest

from packages.contracts.personalization import GoalStatus
from services.personalization.goal_tracker import GoalTracker
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def goal_tracker() -> GoalTracker:
    store = UserModelStore(db_path=":memory:")
    return GoalTracker(user_model_store=store)


@pytest.mark.asyncio
async def test_create_and_match_goal(goal_tracker: GoalTracker) -> None:
    goal = await goal_tracker.create_or_update_goal(
        title="Migrate HRMS backend",
        description="Port MongoDB models to SQLite/PostgreSQL",
        priority=1,
        active_project_path="services/hrms",
        tags=["hrms", "migration", "backend"],
        user_id="user_dev",
    )
    assert goal.title == "Migrate HRMS backend"
    assert goal.status == GoalStatus.ACTIVE

    # Query matching keywords
    matched = await goal_tracker.match_goal_by_query(
        query="Let's work on the HRMS project", user_id="user_dev"
    )
    assert matched is not None
    assert matched.goal_id == goal.goal_id


@pytest.mark.asyncio
async def test_conversational_goal_continuity_continue_project(
    goal_tracker: GoalTracker,
) -> None:
    # Set up active goal
    await goal_tracker.create_or_update_goal(
        title="Implement Voice Barge-In",
        active_project_path="services/voice_gateway",
        priority=1,
        user_id="user_dev2",
    )

    # User says: "Continue the project we were working on"
    matched = await goal_tracker.match_goal_by_query(
        query="Continue the project we were working on", user_id="user_dev2"
    )
    assert matched is not None
    assert matched.title == "Implement Voice Barge-In"


@pytest.mark.asyncio
async def test_update_goal_progress(goal_tracker: GoalTracker) -> None:
    goal = await goal_tracker.create_or_update_goal(
        title="Phase 15 Completion",
        priority=1,
        user_id="user_dev3",
    )
    updated = await goal_tracker.update_goal_progress(
        goal_id=goal.goal_id,
        milestone_title="Implemented User Model",
        completed=True,
        user_id="user_dev3",
    )
    assert len(updated.milestones) == 1
    assert updated.milestones[0]["title"] == "Implemented User Model"
    assert updated.milestones[0]["completed"] is True
