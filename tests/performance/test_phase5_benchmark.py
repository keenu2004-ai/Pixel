"""Performance Benchmarks for Phase 5 Semantic Coding and Desktop Capabilities."""

import time
from pathlib import Path

import pytest

from services.coding.serena_bridge import SerenaBridge
from services.computer_control.desktop_adapter import DesktopAdapter
from services.computer_control.tools import GetActiveWindowTool
from services.intent_engine.parser import DeterministicIntentParser


def test_serena_bridge_symbol_search_latency(tmp_path: Path) -> None:
    # Generate 20 python files with multiple symbols
    for i in range(20):
        code = f"""
def compute_metric_{i}(a: int, b: int) -> int:
    '''Calculates metric {i}.'''
    return a + b * {i}

class MetricCalculator_{i}:
    def calculate(self, val: int) -> int:
        return val * 10
"""
        (tmp_path / f"metric_{i}.py").write_text(code, encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)

    start = time.perf_counter()
    results = bridge.search_symbols("compute_metric_10")
    duration_ms = (time.perf_counter() - start) * 1000

    assert len(results) >= 1
    assert duration_ms < 500.0, f"Symbol search too slow: {duration_ms:.2f}ms"


def test_deterministic_fast_path_zero_regression() -> None:
    """Ensures deterministic fast-path intent matching remains sub-millisecond (< 0.5ms)."""
    parser = DeterministicIntentParser()

    # Warmup
    parser.parse_intent("turn off volume")

    latencies = []
    for _ in range(100):
        start = time.perf_counter()
        res = parser.parse_intent("set volume to 50 percent")
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 0.5, f"Fast path latency regressed: {avg_latency:.4f}ms (must be < 0.5ms)"
    assert res is not None


@pytest.mark.asyncio
async def test_desktop_tool_dispatch_latency() -> None:
    adapter = DesktopAdapter(mock_mode=True)
    tool = GetActiveWindowTool(adapter=adapter)

    start = time.perf_counter()
    res = await tool.execute({}, session_id="bench_s")
    duration_ms = (time.perf_counter() - start) * 1000

    assert res.success is True
    assert duration_ms < 10.0, f"Desktop tool dispatch too slow: {duration_ms:.2f}ms"
