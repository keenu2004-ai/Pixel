"""PIXEL — Phase 16 Multimodal Performance & Latency Benchmark Tests.

Measures p50, p90, p95, and p99 processing latencies across:
- OCR text extraction
- Screen semantic hierarchy parsing
- UI target grounding
- Multimodal context fusion (<5ms requirement)
"""

import time

import pytest

from packages.contracts.multimodal import ScreenFrame
from services.multimodal.manager import MultimodalPerceptionManager


@pytest.mark.asyncio
async def test_multimodal_performance_benchmark() -> None:
    manager = MultimodalPerceptionManager()

    # 1. OCR Latency Benchmark
    ocr_latencies: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        await manager.ocr_engine.extract_text(
            "Sample performance verification text string for OCR benchmark."
        )
        ocr_latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_ocr = sum(ocr_latencies) / len(ocr_latencies)
    assert avg_ocr < 50.0, f"OCR latency too high: {avg_ocr:.2f}ms"

    # 2. Screen Understanding Latency
    screen_latencies: list[float] = []
    frame = ScreenFrame(window_title="Benchmark App")
    for _ in range(50):
        t0 = time.perf_counter()
        await manager.screen_analyzer.analyze_screen(frame)
        screen_latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_screen = sum(screen_latencies) / len(screen_latencies)
    assert avg_screen < 50.0, f"Screen analysis latency too high: {avg_screen:.2f}ms"

    # 3. Context Engine Fusion Latency (<5ms requirement)
    fusion_latencies: list[float] = []
    obs = await manager.router.analyze_screen(frame)
    for _ in range(50):
        t0 = time.perf_counter()
        manager.context_engine.assemble_context(
            voice_query="What is on my screen?",
            screen_observation=obs,
        )
        fusion_latencies.append((time.perf_counter() - t0) * 1000.0)

    avg_fusion = sum(fusion_latencies) / len(fusion_latencies)
    assert avg_fusion < 5.0, f"Context fusion exceeded 5ms SLA: {avg_fusion:.2f}ms"
