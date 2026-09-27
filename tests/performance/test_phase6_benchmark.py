"""Performance Benchmarks for Phase 6 Mobile Gateway & Device Transport."""

import time

import pytest

from packages.contracts.mobile import MobileDeviceMetadata, MobileRegistrationRequest
from services.intent_engine.parser import DeterministicIntentParser
from services.voice_gateway.mobile_adapter import MobileGatewayAdapter
from services.voice_gateway.mock_mobile_device import MockAndroidDeviceRuntime


@pytest.mark.asyncio
async def test_mobile_registration_handshake_latency() -> None:
    adapter = MobileGatewayAdapter(shared_auth_secret="bench_secret_key")

    meta = MobileDeviceMetadata(device_id="bench_device_001")
    req = MobileRegistrationRequest(
        device_id="bench_device_001",
        auth_token="bench_secret_key",
        device_metadata=meta,
    )

    latencies = []
    for _ in range(50):
        start = time.perf_counter()
        res = await adapter.register_device(req)
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    assert res.success is True
    assert avg_latency < 5.0, (
        f"Registration latency too high: {avg_latency:.4f}ms (must be < 5.0ms)"
    )


@pytest.mark.asyncio
async def test_mobile_audio_dispatch_latency() -> None:
    adapter = MobileGatewayAdapter()
    device = MockAndroidDeviceRuntime(adapter=adapter)
    await device.connect_to_gateway()

    dummy_pcm = b"\x00\x00" * 320

    latencies = []
    for _ in range(50):
        start = time.perf_counter()
        res = await device.stream_audio_chunk(dummy_pcm)
        latencies.append((time.perf_counter() - start) * 1000)

    avg_latency = sum(latencies) / len(latencies)
    assert res["status"] == "processed"
    assert avg_latency < 2.0, (
        f"Audio dispatch latency too high: {avg_latency:.4f}ms (must be < 2.0ms)"
    )


def test_deterministic_fast_path_zero_regression_phase6() -> None:
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
    assert avg_latency < 0.5, (
        f"Fast path latency regressed in Phase 6: {avg_latency:.4f}ms (must be < 0.5ms)"
    )
    assert res is not None
