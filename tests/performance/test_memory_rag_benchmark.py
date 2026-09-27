"""Performance benchmarks for PIXEL Layered Memory and RAG Subsystems."""

import tempfile
import time

import pytest

from services.memory.manager import MemoryManager
from services.memory.stores.sqlite_store import SQLiteMemoryStore
from services.rag.chunking.ast_chunker import ASTCodeChunker
from services.rag.retriever import RAGRetriever


@pytest.mark.asyncio
async def test_memory_and_rag_performance_benchmarks() -> None:
    temp_mem = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    temp_rag = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name

    store = SQLiteMemoryStore(db_path=temp_mem)
    mem_mgr = MemoryManager(store=store)
    retriever = RAGRetriever(db_path=temp_rag)
    ast_chunker = ASTCodeChunker()

    # 0. Benchmark Working Memory Updates (100 turns)
    for i in range(100):
        await mem_mgr.record_interaction(
            user_input=f"Turn {i}",
            agent_response=f"Response {i}",
            session_id="bench_sess",
            user_id="bench_user",
        )

    # 1. Benchmark Semantic Fact Writes (100 writes)
    start_time = time.perf_counter()
    for i in range(100):
        await store.set_fact(key=f"user.pref_{i}", value=f"value_{i}", user_id="bench_user")
    fact_write_total_ms = (time.perf_counter() - start_time) * 1000
    avg_fact_write_ms = fact_write_total_ms / 100

    # 2. Benchmark Episodic Memory Embed & Persist (20 episodes)
    start_time = time.perf_counter()
    for i in range(20):
        await store.record_episode(
            summary=f"User interaction log number {i} discussing software architecture.",
            session_id=f"sess_{i}",
            user_id="bench_user",
        )
    ep_write_total_ms = (time.perf_counter() - start_time) * 1000
    avg_ep_write_ms = ep_write_total_ms / 20

    # 3. Benchmark Episodic Search (50 queries)
    start_time = time.perf_counter()
    for _ in range(50):
        await store.search_episodic(query="software architecture interaction", user_id="bench_user", limit=3)
    ep_search_total_ms = (time.perf_counter() - start_time) * 1000
    avg_ep_search_ms = ep_search_total_ms / 50

    # 4. Benchmark AST Python Code Chunking (500-line sample)
    sample_code = """
class CorePipeline:
    def __init__(self, name: str) -> None:
        self.name = name

    def execute(self, task_id: int) -> bool:
        return task_id > 0
""" * 50
    start_time = time.perf_counter()
    for _ in range(20):
        ast_chunker.chunk_text(sample_code, source_uri="bench/core.py")
    ast_total_ms = (time.perf_counter() - start_time) * 1000
    avg_ast_chunk_ms = ast_total_ms / 20

    # 5. Benchmark RAG Ingestion and Hybrid Retrieval
    doc = "# Architecture Guide\nPIXEL provides low latency voice perception and autonomous tool dispatch.\n" * 10
    await retriever.index_text(doc, source_uri="docs/guide.md")

    start_time = time.perf_counter()
    for _ in range(20):
        await retriever.retrieve_and_assemble(query="voice perception low latency", max_tokens=500)
    rag_query_total_ms = (time.perf_counter() - start_time) * 1000
    avg_rag_query_ms = rag_query_total_ms / 20

    print("\n--- PIXEL Phase 3 Performance Benchmarks ---")
    print(f"Average Fact Write Latency: {avg_fact_write_ms:.3f} ms")
    print(f"Average Episodic Embed+Write Latency: {avg_ep_write_ms:.3f} ms")
    print(f"Average Episodic Search Latency: {avg_ep_search_ms:.3f} ms")
    print(f"Average AST Parsing & Chunking Latency (500 lines): {avg_ast_chunk_ms:.3f} ms")
    print(f"Average RAG Hybrid Retrieval & Context Assembly Latency: {avg_rag_query_ms:.3f} ms")

    # SLA Assertions
    assert avg_fact_write_ms < 50.0  # < 50ms
    assert avg_ep_search_ms < 50.0   # < 50ms
    assert avg_ast_chunk_ms < 100.0  # < 100ms
    assert avg_rag_query_ms < 100.0  # < 100ms
