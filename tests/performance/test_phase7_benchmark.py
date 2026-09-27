"""Performance benchmarks for Phase 7 Orchestration & Topology."""

import time

import pytest

from packages.contracts.orchestration import (
    DeviceCapability,
    DeviceRole,
    PairingConfirmation,
    PairingRequest,
    WakeArbitrationCandidate,
)
from services.intent_engine.engine import DeterministicIntentEngine
from services.orchestration.arbitration import WakeArbiter
from services.orchestration.handoff import HandoffManager
from services.orchestration.pki import PKIEngine
from services.orchestration.registry import DeviceRegistry, PresenceManager
from services.os_control.mock_adapter import MockOSAdapter


def test_pairing_and_pki_latency_benchmark() -> None:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)

    req = PairingRequest(
        device_id="sat-bench-1",
        device_name="Benchmark Satellite",
        device_role=DeviceRole.SATELLITE_MIC_SPEAKER,
        capabilities=[DeviceCapability.MICROPHONE, DeviceCapability.SPEAKER],
        public_key_pem="public-key-bench",
    )

    t0 = time.perf_counter()
    chal = registry.initiate_pairing(req)
    conf = PairingConfirmation(
        challenge_id=chal.challenge_id,
        device_id=req.device_id,
        pin_code=chal.pin_code,
        user_confirmed=True,
    )
    resp = registry.complete_pairing(conf)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert resp.success is True
    assert elapsed_ms < 10.0, f"Pairing cycle took {elapsed_ms:.2f}ms, expected < 10ms"


def test_wake_arbitration_5_satellites_latency_benchmark() -> None:
    arbiter = WakeArbiter()
    candidates = [
        WakeArbitrationCandidate(
            device_id=f"sat-{i}",
            wake_event_id="wake-bench-group",
            timestamp_ms=1000 + i * 5,
            confidence=0.90 + (0.01 * i),
            snr_db=15.0 + i,
            estimated_distance_m=1.0 + (i * 0.5),
            rtt_ms=5.0 + i,
        )
        for i in range(5)
    ]

    t0 = time.perf_counter()
    for cand in candidates:
        arbiter.register_candidate(cand)
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert elapsed_ms < 5.0, f"Arbitration across 5 satellites took {elapsed_ms:.2f}ms, expected < 5ms"


def test_context_handoff_latency_benchmark() -> None:
    pki = PKIEngine()
    registry = DeviceRegistry(pki_engine=pki)
    presence = PresenceManager()

    for dev_id in ["pc-bench", "phone-bench"]:
        req = PairingRequest(
            device_id=dev_id,
            device_name=dev_id,
            device_role=DeviceRole.PRIMARY_PC if "pc" in dev_id else DeviceRole.MOBILE_NODE,
            capabilities=[DeviceCapability.DESKTOP_CONTROL, DeviceCapability.ANDROID_CONTROL],
            public_key_pem="pem",
        )
        chal = registry.initiate_pairing(req)
        registry.complete_pairing(PairingConfirmation(challenge_id=chal.challenge_id, device_id=dev_id, pin_code=chal.pin_code, user_confirmed=True))
        presence.update_heartbeat(dev_id)

    handoff = HandoffManager(registry=registry, presence=presence)

    large_context = {
        "dialog_history": [{"speaker": "user", "text": f"turn {i}"} for i in range(50)],
        "auth_token": "secret",
        "api_key": "secret_key",
        "metadata": {"task": "report_generation"},
    }

    t0 = time.perf_counter()
    res = handoff.initiate_context_handoff(
        source_device_id="phone-bench",
        target_device_id="pc-bench",
        session_id="session-bench",
        conversation_context=large_context,
    )
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert "auth_token" not in res.conversation_context
    assert elapsed_ms < 5.0, f"Context handoff took {elapsed_ms:.2f}ms, expected < 5ms"


@pytest.mark.asyncio
async def test_zero_regression_on_deterministic_intent_engine() -> None:
    engine = DeterministicIntentEngine(os_adapter=MockOSAdapter())
    t0 = time.perf_counter()
    resp, packet, result = await engine.handle_transcript("volume 80 percent karo", session_id="bench_sess")
    t1 = time.perf_counter()

    elapsed_ms = (t1 - t0) * 1000.0
    assert len(resp) > 0
    assert elapsed_ms < 50.0, f"Deterministic intent handle took {elapsed_ms:.3f}ms, expected < 50ms"

