"""Unit tests for ContinuousSoakRunner and ReadinessEvaluator."""

import pytest

from packages.contracts.readiness import ReadinessStatus, VerificationLevel
from services.observability.readiness_evaluator import ReadinessEvaluator
from services.observability.soak_runner import ContinuousSoakRunner


@pytest.mark.asyncio
async def test_continuous_soak_runner() -> None:
    runner = ContinuousSoakRunner(target_hours=24.0)
    result = await runner.run_simulated_soak(cycles_count=5, cycle_delay_sec=0.001)

    assert result.passed
    assert result.total_requests == 43
    assert result.successful_requests == 43
    assert result.failed_requests == 0
    assert result.crashes_detected == 0
    assert result.memory_growth_mb < 5.0
    assert result.verification_level == VerificationLevel.LEVEL_5_LONG_RUN_SOAK


def test_readiness_evaluator_scorecard() -> None:
    scorecard = ReadinessEvaluator.evaluate_scorecard(
        security_attacks_blocked=30,
        privacy_violations=0,
        false_success_count=0,
    )

    assert scorecard.overall_classification == ReadinessStatus.READY
    assert scorecard.wake_success_rate >= 0.95
    assert scorecard.stt_command_accuracy >= 0.95
    assert scorecard.security_attacks_blocked == 30
    assert scorecard.privacy_violations_detected == 0
    assert scorecard.false_success_events == 0
