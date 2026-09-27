"""Unit tests for SQLite Memory Store (Semantic & Episodic Tiers)."""

from pathlib import Path

import pytest

from services.memory.stores.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def store(tmp_path: Path) -> SQLiteMemoryStore:
    db_file = tmp_path / "test_memory.db"
    return SQLiteMemoryStore(db_path=str(db_file))


@pytest.mark.asyncio
async def test_semantic_fact_lifecycle_and_supersede(store: SQLiteMemoryStore) -> None:
    # 1. Set initial preference
    f1 = await store.set_fact(
        key="user.preferred_editor",
        value="VS Code",
        user_id="u1",
        category="preference",
    )
    assert f1.key == "user.preferred_editor"
    assert f1.value == "VS Code"

    val1 = await store.get_fact(key="user.preferred_editor", user_id="u1")
    assert val1 == "VS Code"

    # 2. Update preference (supersede)
    f2 = await store.set_fact(
        key="user.preferred_editor",
        value="Cursor",
        user_id="u1",
        category="preference",
    )
    assert f2.value == "Cursor"

    # Active value must be Cursor
    val2 = await store.get_fact(key="user.preferred_editor", user_id="u1")
    assert val2 == "Cursor"

    # List facts should only contain active fact
    active_facts = await store.list_facts(user_id="u1")
    assert len(active_facts) == 1
    assert active_facts[0].value == "Cursor"


@pytest.mark.asyncio
async def test_episodic_memory_embedding_and_search(store: SQLiteMemoryStore) -> None:
    await store.record_episode(
        summary="User discussed migrating voice pipeline from mock to faster-whisper.",
        session_id="sess_1",
        user_id="u1",
    )
    await store.record_episode(
        summary="User ordered pizza for lunch.",
        session_id="sess_2",
        user_id="u1",
    )

    # Search for voice/whisper discussion
    results = await store.search_episodic(
        query="whisper voice transcription", user_id="u1", limit=2
    )
    assert len(results) >= 1
    assert "faster-whisper" in results[0]["summary"]


@pytest.mark.asyncio
async def test_right_to_forget_cryptographic_purge(store: SQLiteMemoryStore) -> None:
    await store.set_fact(key="user.secret_project", value="Project Titan", user_id="u1")
    await store.record_episode(
        summary="User discussed confidential architecture for Project Titan.",
        session_id="sess_3",
        user_id="u1",
    )

    # Verify presence
    assert await store.get_fact("user.secret_project", "u1") == "Project Titan"

    # Right to Forget: purge "Titan"
    purged = await store.forget_topic(keyword="Titan", user_id="u1")
    assert purged >= 2

    # Verify complete deletion
    assert await store.get_fact("user.secret_project", "u1") is None
    res = await store.search_episodic(query="Project Titan", user_id="u1")
    assert len(res) == 0
