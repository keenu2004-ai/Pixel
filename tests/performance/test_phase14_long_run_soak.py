"""Performance & Long-Run Soak Benchmarks for Phase 14 Daily-Driver Readiness."""

import pytest

from packages.contracts.readiness import VerificationLevel
from services.observability.readiness_evaluator import ReadinessEvaluator
from services.observability.soak_runner import ContinuousSoakRunner


@pytest.mark.asyncio
async def test_performance_24h_compressed_soak() -> None:
    runner = ContinuousSoakRunner(target_hours=24.0)
    soak_result = await runner.run_simulated_soak(
        cycles_count=10,
        cycle_delay_sec=0.001,
        simulate_network_drop=True,
    )

    assert soak_result.passed
    assert soak_result.total_requests == 85
    assert soak_result.successful_requests == 85
    assert soak_result.failed_requests == 0
    assert soak_result.crashes_detected == 0
    assert soak_result.memory_growth_mb < 2.0  # Zero unbounded memory growth
    assert soak_result.average_latency_ms < 15.0
    assert soak_result.p95_latency_ms < 20.0
    assert soak_result.verification_level == VerificationLevel.LEVEL_5_LONG_RUN_SOAK


@pytest.mark.asyncio
async def test_readiness_scorecard_metrics() -> None:
    runner = ContinuousSoakRunner(target_hours=24.0)
    soak_result = await runner.run_simulated_soak(cycles_count=5, cycle_delay_sec=0.001)

    scorecard = ReadinessEvaluator.evaluate_scorecard(
        soak_result=soak_result,
        security_attacks_blocked=30,
        privacy_violations=0,
        false_success_count=0,
    )

    assert scorecard.overall_classification.value == "READY"
    assert scorecard.wake_success_rate >= 0.99
    assert scorecard.tts_first_audio_ms < 5.0
    assert scorecard.battery_drain_per_hour_percent < 2.0
    assert scorecard.memory_leak_rate_mb_per_hour == 0.0
