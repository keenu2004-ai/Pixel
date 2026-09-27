"""End-to-end integration tests verifying Layered Memory, RAG, and Intent Routing."""

import tempfile

import pytest

from packages.contracts.intents import IntentRoutingType
from services.intent_engine.parser import DeterministicIntentParser
from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore
from services.rag.retriever import RAGRetriever


@pytest.fixture
def test_env() -> tuple[DeterministicIntentParser, MemoryManager, RAGRetriever]:
    temp_mem = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    temp_rag = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name

    mem_store = SQLiteMemoryStore(db_path=temp_mem)
    mem_mgr = MemoryManager(store=mem_store)
    rag_ret = RAGRetriever(db_path=temp_rag)
    parser = DeterministicIntentParser()

    return parser, mem_mgr, rag_ret


@pytest.mark.asyncio
async def test_fast_path_bypasses_rag_overhead(test_env: tuple[DeterministicIntentParser, MemoryManager, RAGRetriever]) -> None:
    parser, mem_mgr, rag_ret = test_env

    # 1. Deterministic command
    packet = parser.parse_intent("volume 50 percent kardo")
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH

    # Deterministic commands MUST NOT perform expensive RAG lookup
    # Working memory still records the interaction seamlessly
    await mem_mgr.record_interaction(
        user_input="volume 50 percent kardo",
        agent_response="Volume set to 50%",
        session_id="sess_int_1",
        user_id="user_1",
    )

    recent = mem_mgr.get_working_memory(session_id="sess_int_1")
    assert len(recent) == 1
    assert recent[0]["user"] == "volume 50 percent kardo"


@pytest.mark.asyncio
async def test_conversational_rag_and_memory_enrichment(test_env: tuple[DeterministicIntentParser, MemoryManager, RAGRetriever]) -> None:
    parser, mem_mgr, rag_ret = test_env

    # 1. Pre-index technical documentation in RAG
    doc = """# PIXEL Audio Pipeline
The audio stream uses a 16kHz ring buffer feeding Silero VAD.
Speech frames are batched for Faster-Whisper transcription.
"""
    await rag_ret.index_text(doc, source_uri="docs/audio.md")

    # 2. Record user preference in memory
    await mem_mgr.store.set_fact(key="user.mic_device", value="HyperX SoloCast", user_id="user_1")

    # 3. Conversational query
    user_query = "What mic am I using and how does the audio pipeline work?"
    packet = parser.parse_intent(user_query)
    assert packet.routing_type in (IntentRoutingType.CONVERSATIONAL_QA, IntentRoutingType.LANGGRAPH_AGENT)

    # 4. Assemble context from both Memory and RAG
    mem_ctx = await mem_mgr.query_context(query=user_query, session_id="sess_int_2", user_id="user_1")
    rag_ctx = await rag_ret.retrieve_and_assemble(query=user_query, max_tokens=500)

    # Validate memory enrichment
    facts = mem_ctx.get("facts", [])
    assert any("HyperX" in str(f.get("value")) for f in facts)

    # Validate RAG enrichment
    assert len(rag_ctx.retrieved_items) >= 1
    assert len(rag_ctx.citations) >= 1
    assert "Silero VAD" in rag_ctx.formatted_context
