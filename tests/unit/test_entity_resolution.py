"""Unit tests for EntityResolver (Personal Vocabulary & Ambiguity Defense)."""

import pytest

from packages.contracts.personalization import EntityType
from services.personalization.entity_resolver import EntityResolver
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def entity_resolver() -> EntityResolver:
    store = UserModelStore(db_path=":memory:")
    return EntityResolver(user_model_store=store)


@pytest.mark.asyncio
async def test_exact_and_alias_entity_resolution(entity_resolver: EntityResolver) -> None:
    await entity_resolver.register_entity(
        canonical_name="Rahul Sharma",
        entity_type=EntityType.PERSON,
        aliases=["rahul", "manager", "lead"],
        context_metadata={"role": "Lead Architect"},
        user_id="user_1",
    )

    # Search by alias
    res = await entity_resolver.resolve_entity("rahul", user_id="user_1")
    assert res.matched is True
    assert res.ambiguous is False
    assert res.resolved_entity is not None
    assert res.resolved_entity.canonical_name == "Rahul Sharma"


@pytest.mark.asyncio
async def test_entity_ambiguity_never_guesses(entity_resolver: EntityResolver) -> None:
    # 2 different contacts named Rahul
    await entity_resolver.register_entity(
        canonical_name="Rahul Sharma",
        entity_type=EntityType.PERSON,
        aliases=["rahul"],
        context_metadata={"relationship": "work manager"},
        user_id="user_2",
    )
    await entity_resolver.register_entity(
        canonical_name="Rahul Verma",
        entity_type=EntityType.PERSON,
        aliases=["rahul"],
        context_metadata={"relationship": "tennis partner"},
        user_id="user_2",
    )

    res = await entity_resolver.resolve_entity("rahul", user_id="user_2")
    # Must NOT guess!
    assert res.matched is False
    assert res.ambiguous is True
    assert len(res.candidate_entities) == 2
    assert res.clarification_prompt is not None
    assert "Which one did you mean?" in res.clarification_prompt
