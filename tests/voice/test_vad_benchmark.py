"""Live Hardware Benchmark for Silero ONNX VAD.

Measures cold-start initialization latency and steady-state warm inference per-frame latency.
Excluded from normal CI via @pytest.mark.voice_hw.
"""

import os
import time

import numpy as np
import pytest

from packages.contracts.events import AudioFrame
from services.voice_gateway.vad.silero_vad import SileroVADConfig, SileroVADProvider


def _generate_synthetic_pcm_frame(num_samples: int = 512, frequency_hz: float = 440.0) -> AudioFrame:
    """Generates a synthetic 16kHz 16-bit mono sine wave PCM frame (32ms)."""
    t = np.linspace(0, num_samples / 16000.0, num_samples, endpoint=False)
    # Sine wave between -0.8 and 0.8
    waveform = 0.8 * np.sin(2 * np.pi * frequency_hz * t)
    pcm_int16 = (waveform * 32767).astype(np.int16)
    return AudioFrame(
        sample_rate=16000,
        channels=1,
        pcm_data=pcm_int16.tobytes(),
        timestamp_ms=int(time.time() * 1000)
    )


@pytest.mark.voice_hw
@pytest.mark.asyncio
async def test_silero_vad_latency_benchmark() -> None:
    model_path = "data/models/silero_vad.onnx"
    if not os.path.exists(model_path):
        pytest.skip(f"Silero VAD model not found at '{model_path}'. Run 'python scripts/bootstrap_models.py' first.")

    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        pytest.skip("onnxruntime is not installed. Install with 'pip install onnxruntime'.")

    config = SileroVADConfig(model_path=model_path)
    test_frame = _generate_synthetic_pcm_frame()

    # 1. Measure Cold Start (Instantiate + Initialize + First Inference)
    cold_start_t0 = time.perf_counter()
    provider = SileroVADProvider(config)
    provider.initialize()
    first_event = await provider.process_frame(test_frame, session_id="bench_cold")
    cold_start_ms = (time.perf_counter() - cold_start_t0) * 1000.0

    assert first_event is not None
    assert provider.is_available() is True

    # 2. Measure Warm Runtime Inference (50 consecutive frames)
    latencies_ms: list[float] = []
    for _i in range(50):
        t0 = time.perf_counter()
        ev = await provider.process_frame(test_frame, session_id="bench_warm")
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)
        assert ev is not None

    avg_warm_ms = float(np.mean(latencies_ms))
    p95_warm_ms = float(np.percentile(latencies_ms, 95))
    min_warm_ms = float(np.min(latencies_ms))
    max_warm_ms = float(np.max(latencies_ms))

    await provider.shutdown()

    print("\n" + "=" * 60)
    print("SILERO ONNX VAD BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Cold-Start Latency (Load + Init + 1st Frame) : {cold_start_ms:.2f} ms")
    print(f"Warm Inference Latency (Average per 32ms frame): {avg_warm_ms:.3f} ms")
    print(f"Warm Inference P95 Latency                    : {p95_warm_ms:.3f} ms")
    print(f"Warm Inference Min / Max                      : {min_warm_ms:.3f} / {max_warm_ms:.3f} ms")
    print("=" * 60)

    # Sanity threshold assertions: Warm inference on CPU should easily be < 10ms per 32ms frame
    assert avg_warm_ms < 15.0, f"Average warm inference latency {avg_warm_ms}ms exceeded 15ms ceiling"
