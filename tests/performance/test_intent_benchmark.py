"""Performance and Latency Benchmark for Phase 2 Deterministic Intent Engine."""

import statistics
import time

import pytest

from services.intent_engine.engine import DeterministicIntentEngine
from services.os_control.mock_adapter import MockOSAdapter


@pytest.mark.asyncio
async def test_deterministic_intent_latency_benchmark() -> None:
    """Measures end-to-end latency of the deterministic execution path."""
    engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())

    test_queries = [
        "kal subah 7 baje alarm laga dena",
        "set a timer for 10 minutes",
        "volume 80 percent karo",
        "Chrome kholo",
        "mujhe shaam 7 baje doodh lene ka reminder set karo",
        "kitne baje hain",
        "what is the date today",
        "awaaz kam kar do",
        "5 min ka timer shuru karo",
        "cancel timer",
    ]

    # Cold Start
    t_cold_start = time.perf_counter()
    resp_cold, _, _ = await engine.handle_transcript(test_queries[0], session_id="cold_sess")
    cold_latency_ms = (time.perf_counter() - t_cold_start) * 1000

    assert len(resp_cold) > 0

    # Warm Runs (100 iterations)
    latencies: list[float] = []
    for i in range(100):
        query = test_queries[i % len(test_queries)]
        t0 = time.perf_counter()
        resp, packet, result = await engine.handle_transcript(query, session_id=f"warm_sess_{i}")
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)
        assert len(resp) > 0

    avg_latency = statistics.mean(latencies)
    median_latency = statistics.median(latencies)
    sorted_latencies = sorted(latencies)
    p95_latency = sorted_latencies[int(len(sorted_latencies) * 0.95)]
    min_latency = min(latencies)
    max_latency = max(latencies)

    print("\n" + "=" * 65)
    print("PIXEL PHASE 2 DETERMINISTIC INTENT BENCHMARK SPECIFICATION")
    print("=" * 65)
    print("Target Threshold    : < 600.00 ms (Zero-LLM Fast Path)")
    print("Test Iterations     : 100 samples across English/Hindi/Hinglish")
    print("-" * 65)
    print(f"Cold-Start Latency  : {cold_latency_ms:.3f} ms")
    print(f"Warm Latency (Avg)  : {avg_latency:.3f} ms")
    print(f"Warm Latency (P50)  : {median_latency:.3f} ms")
    print(f"Warm Latency (P95)  : {p95_latency:.3f} ms")
    print(f"Warm Latency (Min)  : {min_latency:.3f} ms")
    print(f"Warm Latency (Max)  : {max_latency:.3f} ms")
    print("=" * 65)

    # Hard assert: Must be well below 600ms target
    assert avg_latency < 600.0, f"Average latency {avg_latency}ms exceeded 600ms limit!"
    assert p95_latency < 600.0, f"P95 latency {p95_latency}ms exceeded 600ms limit!"
