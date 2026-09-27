"""Live Hardware Benchmark for Silero ONNX VAD.

Measures cold-start initialization latency and steady-state warm inference per-frame latency.
Excluded from normal CI via @pytest.mark.voice_hw.
"""

import hashlib
import os
import time

import numpy as np
import pytest

from packages.contracts.events import AudioFrame
from services.voice_gateway.vad.silero_vad import (
    SILERO_V5_OFFICIAL_SHA256,
    SileroVADConfig,
    SileroVADProvider,
)


def _generate_synthetic_pcm_frame(
    num_samples: int = 512, frequency_hz: float = 440.0
) -> AudioFrame:
    """Generates a synthetic 16kHz 16-bit mono sine wave PCM frame (32ms)."""
    t = np.linspace(0, num_samples / 16000.0, num_samples, endpoint=False)
    # Sine wave between -0.8 and 0.8
    waveform = 0.8 * np.sin(2 * np.pi * frequency_hz * t)
    pcm_int16 = (waveform * 32767).astype(np.int16)
    return AudioFrame(
        sample_rate=16000,
        channels=1,
        pcm_data=pcm_int16.tobytes(),
        timestamp_ms=int(time.time() * 1000),
    )


@pytest.mark.voice_hw
@pytest.mark.asyncio
async def test_silero_vad_latency_benchmark() -> None:
    model_path = "data/models/silero_vad.onnx"
    if not os.path.exists(model_path):
        pytest.skip(
            f"Silero VAD model not found at '{model_path}'. Run 'python scripts/bootstrap_models.py' first."
        )

    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        pytest.skip("onnxruntime is not installed. Install with 'pip install onnxruntime'.")

    # Verify model checksum
    sha256 = hashlib.sha256()
    with open(model_path, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    actual_hash = sha256.hexdigest().lower()
    assert actual_hash == SILERO_V5_OFFICIAL_SHA256.lower(), (
        "Local model failed SHA-256 integrity check!"
    )

    config = SileroVADConfig(model_path=model_path, expected_sha256=SILERO_V5_OFFICIAL_SHA256)
    test_frame = _generate_synthetic_pcm_frame()
    file_size_mb = os.path.getsize(model_path) / (1024 * 1024)

    # 1. Measure Cold Start (Instantiate + Initialize + First Inference)
    cold_start_t0 = time.perf_counter()
    provider = SileroVADProvider(config)
    provider.initialize()
    first_event = await provider.process_frame(test_frame, session_id="bench_cold")
    cold_start_ms = (time.perf_counter() - cold_start_t0) * 1000.0

    assert first_event is not None
    assert 0.0 <= first_event.speech_probability <= 1.0
    assert provider.is_available() is True

    # 2. Measure Warm Runtime Inference (50 consecutive frames)
    latencies_ms: list[float] = []
    for _i in range(50):
        t0 = time.perf_counter()
        ev = await provider.process_frame(test_frame, session_id="bench_warm")
        dt_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(dt_ms)
        assert ev is not None
        assert 0.0 <= ev.speech_probability <= 1.0

    avg_warm_ms = float(np.mean(latencies_ms))
    p95_warm_ms = float(np.percentile(latencies_ms, 95))
    min_warm_ms = float(np.min(latencies_ms))
    max_warm_ms = float(np.max(latencies_ms))

    await provider.shutdown()

    print("\n" + "=" * 65)
    print("PIXEL SILERO ONNX VAD BENCHMARK SPECIFICATION")
    print("=" * 65)
    print(f"Model Path           : {model_path} ({file_size_mb:.2f} MB)")
    print(f"SHA-256 Digest       : {actual_hash[:16]}... (Verified Official v5)")
    print("Execution Provider   : CPUExecutionProvider (Single-Threaded)")
    print("Audio Frame Spec     : PCM 16-bit Mono @ 16kHz (512 samples / 32ms)")
    print("Warm Iterations      : 50 frames")
    print("-" * 65)
    print(f"Cold-Start Latency   : {cold_start_ms:.2f} ms (Load + Session + 1st Frame)")
    print(
        f"Warm Inference (Avg) : {avg_warm_ms:.3f} ms / frame (~{32.0 / avg_warm_ms:.1f}x Real-time)"
    )
    print(f"Warm Inference (P95) : {p95_warm_ms:.3f} ms / frame")
    print(f"Warm Inference Min   : {min_warm_ms:.3f} ms")
    print(f"Warm Inference Max   : {max_warm_ms:.3f} ms")
    print("=" * 65)

    # Sanity threshold assertions: Warm inference on CPU must easily be < 15ms per 32ms frame
    assert avg_warm_ms < 15.0, (
        f"Average warm inference latency {avg_warm_ms}ms exceeded 15ms ceiling"
    )
