"""End-to-End Integration tests verifying LangGraph Agent Runtime, Intent Routing, and Fast-Path Bypass."""

import tempfile
from pathlib import Path

import pytest

from packages.contracts.agent import AgentExecutionStatus
from packages.contracts.intents import IntentRoutingType
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer
from services.agent_runtime.engine import AgentRuntimeEngine
from services.intent_engine.engine import DeterministicIntentEngine
from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore
from services.os_control.mock_adapter import MockOSAdapter
from services.rag.retriever import RAGRetriever


@pytest.fixture
def test_environment() -> tuple[
    DeterministicIntentEngine, AgentRuntimeEngine, MemoryManager, RAGRetriever
]:
    temp_mem = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    temp_rag = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    temp_cp = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name

    mem_store = SQLiteMemoryStore(db_path=temp_mem)
    mem_mgr = MemoryManager(store=mem_store)
    rag_ret = RAGRetriever(db_path=temp_rag)
    os_adapter = MockOSAdapter()
    checkpointer = SQLiteCheckpointer(db_path=temp_cp)

    agent_engine = AgentRuntimeEngine(
        os_adapter=os_adapter,
        memory_manager=mem_mgr,
        rag_retriever=rag_ret,
        checkpointer=checkpointer,
    )

    intent_engine = DeterministicIntentEngine(
        os_adapter=os_adapter,
        memory_manager=mem_mgr,
        rag_retriever=rag_ret,
        agent_engine=agent_engine,
    )

    return intent_engine, agent_engine, mem_mgr, rag_ret


@pytest.mark.asyncio
async def test_fast_path_intent_bypasses_agent_runtime(
    test_environment: tuple[
        DeterministicIntentEngine, AgentRuntimeEngine, MemoryManager, RAGRetriever
    ],
) -> None:
    intent_engine, agent_engine, mem_mgr, _ = test_environment

    # Deterministic Command
    transcript = "volume 60 percent kardo"
    response, packet, result = await intent_engine.handle_transcript(
        transcript_text=transcript,
        session_id="sess_fast_1",
    )

    # Must route to DETERMINISTIC_FAST_PATH
    assert packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH
    assert "60%" in response
    assert result.success is True

    # Checkpoint store must have 0 agent task records for this fast-path command
    cps = await agent_engine.checkpointer.list_checkpoints("sess_fast_1")
    assert len(cps) == 0


@pytest.mark.asyncio
async def test_multi_step_agent_execution_with_rag_and_memory(
    test_environment: tuple[
        DeterministicIntentEngine, AgentRuntimeEngine, MemoryManager, RAGRetriever
    ],
) -> None:
    intent_engine, agent_engine, mem_mgr, rag_ret = test_environment

    # 1. Pre-index technical documentation
    doc = """# PIXEL Audio Stream Architecture
The audio pipeline runs at 16000Hz 16-bit PCM.
It feeds a Silero VAD ONNX model for real-time speech boundary detection.
"""
    await rag_ret.index_text(doc, source_uri="docs/audio_stream.md")

    # 2. Execute multi-step task
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "pipeline_summary.txt"
        query = f"Find information about audio stream architecture and save to {out_file}"

        state = await agent_engine.execute_task(
            user_query=query,
            session_id="sess_multi_1",
            user_id="u_multi_1",
        )

        assert state.status == AgentExecutionStatus.SUCCESS
        assert len(state.tool_history) >= 2  # search_knowledge then write_file
        assert out_file.exists()
        file_text = out_file.read_text(encoding="utf-8")
        assert "Silero VAD" in file_text or "16000Hz" in file_text
