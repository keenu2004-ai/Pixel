"""Unit tests for MemoryManager (Working Memory + Background Extraction + Aggregation)."""

import asyncio
import tempfile

import pytest

from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore


@pytest.fixture
def temp_db_path() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return f.name


@pytest.fixture
def memory_manager(temp_db_path: str) -> MemoryManager:
    store = SQLiteMemoryStore(db_path=temp_db_path)
    return MemoryManager(store=store, working_memory_capacity=5)


@pytest.mark.asyncio
async def test_working_memory_ring_buffer(memory_manager: MemoryManager) -> None:
    session_id = "sess_test_1"
    user_id = "u_test_1"

    for i in range(7):
        await memory_manager.record_interaction(
            user_input=f"User msg {i}",
            agent_response=f"Agent resp {i}",
            session_id=session_id,
            user_id=user_id,
        )

    # Allow brief moment for background extraction task to process if needed
    await asyncio.sleep(0.05)

    recent = memory_manager.get_working_memory(session_id=session_id)
    # Capacity is 5, so only the last 5 turns should be present (2, 3, 4, 5, 6)
    assert len(recent) == 5
    assert recent[0]["user"] == "User msg 2"
    assert recent[-1]["user"] == "User msg 6"


@pytest.mark.asyncio
async def test_background_extraction_and_query_aggregation(memory_manager: MemoryManager) -> None:
    session_id = "sess_test_2"
    user_id = "u_test_2"

    # User expresses preference
    await memory_manager.record_interaction(
        user_input="My favorite editor is Neovim and I use dark mode.",
        agent_response="Noted! Neovim with dark mode is configured.",
        session_id=session_id,
        user_id=user_id,
    )

    # Await background queue processing
    await asyncio.sleep(0.1)

    # Context query
    ctx = await memory_manager.query_context(
        query="What editor does the user prefer?",
        session_id=session_id,
        user_id=user_id,
    )

    assert "working_context" in ctx
    assert len(ctx["working_context"]) >= 1
    assert "facts" in ctx
    # Facts extracted from background extractor
    facts = ctx["facts"]
    assert any(
        "neovim" in str(f.get("value")).lower() or "editor" in f.get("key", "") for f in facts
    )


@pytest.mark.asyncio
async def test_memory_right_to_forget(memory_manager: MemoryManager) -> None:
    session_id = "sess_test_3"
    user_id = "u_test_3"

    await memory_manager.store.set_fact(
        key="user.confidential_key", value="SecretValue42", user_id=user_id
    )
    await memory_manager.record_interaction(
        user_input="Remember that my SecretValue42 is stored.",
        agent_response="I have recorded it.",
        session_id=session_id,
        user_id=user_id,
    )
    await asyncio.sleep(0.05)

    # Purge topic
    purged_count = await memory_manager.forget_topic(keyword="SecretValue42", user_id=user_id)
    assert purged_count >= 1

    # Verify fact is gone
    val = await memory_manager.store.get_fact(key="user.confidential_key", user_id=user_id)
    assert val is None
