"""Unit tests for UserModel and UserModelStore persistence."""

import pytest

from packages.contracts.personalization import (
    AssistantTone,
    EntityType,
    HabitPattern,
    LanguageMode,
    PatternStatus,
    PersonalEntity,
    PersonalGoal,
    ResponseLengthPreference,
    RoutineStep,
    UserRoutine,
)
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def user_store() -> UserModelStore:
    return UserModelStore(db_path=":memory:")


@pytest.mark.asyncio
async def test_user_model_default_initialization(user_store: UserModelStore) -> None:
    model = await user_store.get_user_model("user_alpha")
    assert model.user_id == "user_alpha"
    assert model.identity.display_name == "User"
    assert model.preferences.preferred_code_editor == "VS Code"
    assert model.preferences.language_mode == LanguageMode.AUTO_DETECT
    assert model.privacy_policy.auto_scrub_pii is True


@pytest.mark.asyncio
async def test_user_model_save_and_reload(user_store: UserModelStore) -> None:
    model = await user_store.get_user_model("user_beta")
    model.identity.display_name = "Vaibhav"
    model.preferences.preferred_code_editor = "PyCharm"
    model.preferences.preferred_browser = "firefox"
    model.preferences.response_length = ResponseLengthPreference.CONCISE
    model.preferences.tone = AssistantTone.CASUAL
    model.preferences.custom_preferences["favorite_theme"] = "dracula"

    await user_store.save_user_model(model)

    reloaded = await user_store.get_user_model("user_beta")
    assert reloaded.identity.display_name == "Vaibhav"
    assert reloaded.preferences.preferred_code_editor == "PyCharm"
    assert reloaded.preferences.preferred_browser == "firefox"
    assert reloaded.preferences.response_length == ResponseLengthPreference.CONCISE
    assert reloaded.preferences.tone == AssistantTone.CASUAL
    assert reloaded.preferences.custom_preferences["favorite_theme"] == "dracula"
    assert reloaded.version >= 2


@pytest.mark.asyncio
async def test_user_model_goals_and_routines_persistence(user_store: UserModelStore) -> None:
    goal = PersonalGoal(
        user_id="user_gamma",
        title="Migrate DB to SQLite",
        priority=1,
        active_project_path="packages/storage",
    )
    await user_store.save_goal(goal)

    routine = UserRoutine(
        user_id="user_gamma",
        name="Morning Standup Setup",
        steps=[RoutineStep(step_id=1, name="open_slack", tool_or_action="launch_app")],
        is_active=True,
    )
    await user_store.save_routine(routine)

    entity = PersonalEntity(
        user_id="user_gamma",
        entity_type=EntityType.PROJECT,
        canonical_name="PIXEL",
        aliases=["pixel", "runtime"],
    )
    await user_store.save_entity(entity)

    habit = HabitPattern(
        user_id="user_gamma",
        name="Nightly build trigger",
        description="User builds before sleep",
        trigger_condition="time:23:00",
        associated_action="run_tests",
        status=PatternStatus.OBSERVED,
    )
    await user_store.save_habit(habit)

    loaded = await user_store.get_user_model("user_gamma")
    assert len(loaded.active_goals) == 1
    assert loaded.active_goals[0].title == "Migrate DB to SQLite"
    assert len(loaded.routines) == 1
    assert loaded.routines[0].name == "Morning Standup Setup"
    assert len(loaded.entities) == 1
    assert loaded.entities[0].canonical_name == "PIXEL"
    assert len(loaded.habits) == 1
    assert loaded.habits[0].name == "Nightly build trigger"


@pytest.mark.asyncio
async def test_user_model_cascade_purge(user_store: UserModelStore) -> None:
    goal = PersonalGoal(user_id="purge_user", title="Secret Project X")
    await user_store.save_goal(goal)

    routine = UserRoutine(user_id="purge_user", name="Secret Routine")
    await user_store.save_routine(routine)

    entity = PersonalEntity(
        user_id="purge_user",
        entity_type=EntityType.PERSON,
        canonical_name="Secret Agent",
        aliases=["agent_x"],
    )
    await user_store.save_entity(entity)

    # Purge by keyword
    purged_count = await user_store.purge_user_data(user_id="purge_user", keyword="Secret")
    assert purged_count >= 3

    model = await user_store.get_user_model("purge_user")
    assert len(model.active_goals) == 0
    assert len(model.routines) == 0
    assert len(model.entities) == 0
