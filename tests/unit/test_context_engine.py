"""Unit tests for ContextEngine (Minimal Relevant Context, Ranking Signals, Token Budget, Latency)."""

import pytest

from packages.contracts.personalization import EntityType
from services.personalization.context_engine import ContextEngine
from services.personalization.entity_resolver import EntityResolver
from services.personalization.goal_tracker import GoalTracker
from services.personalization.preference_engine import PreferenceEngine
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def context_env() -> tuple[ContextEngine, PreferenceEngine, GoalTracker, EntityResolver]:
    store = UserModelStore(db_path=":memory:")
    pe = PreferenceEngine(user_model_store=store)
    gt = GoalTracker(user_model_store=store)
    er = EntityResolver(user_model_store=store)
    ce = ContextEngine(
        user_model_store=store,
        preference_engine=pe,
        goal_tracker=gt,
        entity_resolver=er,
        max_context_items=4,
    )
    return ce, pe, gt, er


@pytest.mark.asyncio
async def test_assemble_minimal_relevant_context(
    context_env: tuple[ContextEngine, PreferenceEngine, GoalTracker, EntityResolver],
) -> None:
    ce, pe, gt, er = context_env

    # 1. Setup preferences
    await pe.set_explicit_preference("preferred_code_editor", "VS Code", user_id="u_ctx")
    await pe.set_explicit_preference("preferred_browser", "Chrome", user_id="u_ctx")

    # 2. Setup active goal
    await gt.create_or_update_goal(
        title="Voice Pipeline Optimization",
        active_project_path="services/voice_gateway",
        user_id="u_ctx",
    )

    # 3. Setup entity
    await er.register_entity(
        canonical_name="PIXEL",
        entity_type=EntityType.PROJECT,
        aliases=["pixel", "runtime"],
        user_id="u_ctx",
    )

    # 4. Assemble context for query "open my editor and check project"
    assembled = await ce.assemble_context(
        query="open my editor and check voice project",
        session_id="sess_1",
        user_id="u_ctx",
    )

    assert assembled.user_id == "u_ctx"
    assert len(assembled.items) > 0
    assert assembled.active_goal_title == "Voice Pipeline Optimization"
    assert assembled.assembly_latency_ms < 50.0  # Ultra-fast
    assert (
        "[MEMORY_DATA" in assembled.injected_facts_summary
        or "[PREFERENCE" in assembled.injected_facts_summary
        or "[GOAL" in assembled.injected_facts_summary
    )
