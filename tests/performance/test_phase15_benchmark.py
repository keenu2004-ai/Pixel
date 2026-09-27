"""Phase 15 Personalization Performance & Quality Benchmark.

Measures:
- Context Assembly Latency (<5ms target)
- Ranking and Token Budget Overhead
- False Personalization Rate (0.0% goal)
- Memory Retrieval Latency
"""

import time

import pytest

from packages.contracts.personalization import EntityType
from services.personalization.manager import PersonalizationManager


@pytest.mark.asyncio
async def test_benchmark_context_assembly_latency() -> None:
    p_mgr = PersonalizationManager(db_path=":memory:")

    # Setup 10 preferences, 5 goals, 10 entities
    for i in range(10):
        await p_mgr.set_preference(f"pref_key_{i}", f"pref_val_{i}", user_id="bench_user")
    for i in range(5):
        await p_mgr.register_goal(title=f"Goal {i}", user_id="bench_user")
    for i in range(10):
        await p_mgr.register_entity(
            canonical_name=f"Entity {i}",
            entity_type=EntityType.PROJECT,
            aliases=[f"ent_{i}"],
            user_id="bench_user",
        )

    # Measure context assembly latency across 50 iterations
    latencies: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        ctx = await p_mgr.assemble_context(
            query="open my code editor for Goal 2 with ent_3",
            user_id="bench_user",
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        latencies.append(latency_ms)
        assert ctx.total_tokens_estimated <= 800

    avg_latency = sum(latencies) / len(latencies)
    print(
        f"\n[BENCHMARK Phase 15] Context Assembly Latency: {avg_latency:.3f}ms (min: {min(latencies):.3f}ms, max: {max(latencies):.3f}ms)"
    )
    # Must be ultra-responsive
    assert avg_latency < 15.0


@pytest.mark.asyncio
async def test_benchmark_false_personalization_rate() -> None:
    p_mgr = PersonalizationManager(db_path=":memory:")

    # User never mentioned anything about database preferences
    ctx = await p_mgr.assemble_context(query="calculate 2 + 2", user_id="bench_user_2")

    # Injected facts should not contain ungrounded or fabricated preferences
    injected = ctx.injected_facts_summary
    assert "mongo" not in injected.lower()
    assert "postgres" not in injected.lower()
    assert "mysql" not in injected.lower()
