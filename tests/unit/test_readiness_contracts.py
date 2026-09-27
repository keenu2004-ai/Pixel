"""Unit tests for Phase 14 readiness contracts and verification levels."""

from packages.contracts.readiness import (
    DailyDriverScorecard,
    DeviceHardwareProfile,
    ProductionConfig,
    ReadinessStatus,
    RollbackState,
    SoakTestResult,
    VerificationLevel,
)


def test_verification_levels() -> None:
    assert VerificationLevel.LEVEL_0_STATIC_UNIT == "LEVEL_0_STATIC_UNIT"
    assert VerificationLevel.LEVEL_5_LONG_RUN_SOAK == "LEVEL_5_LONG_RUN_SOAK"


def test_device_hardware_profile() -> None:
    profile = DeviceHardwareProfile(
        device_model="Pixel 8 Pro",
        os_name="Android 14",
        cpu_cores=8,
        ram_mb=12288,
        battery_level_percent=92,
        is_charging=False,
        granted_permissions=["RECORD_AUDIO", "CALL_PHONE"],
        verification_level=VerificationLevel.LEVEL_4_PHYSICAL_DEVICE,
    )
    assert profile.device_model == "Pixel 8 Pro"
    assert profile.verification_level == VerificationLevel.LEVEL_4_PHYSICAL_DEVICE
    assert profile.cpu_cores == 8


def test_soak_test_result() -> None:
    soak = SoakTestResult(
        duration_seconds=3600.0,
        total_requests=500,
        successful_requests=500,
        failed_requests=0,
        memory_start_mb=120.0,
        memory_end_mb=120.5,
        memory_growth_mb=0.5,
        crashes_detected=0,
        reconnections_count=2,
        duplicate_actions_prevented=2,
        average_latency_ms=4.5,
        p95_latency_ms=8.2,
        p99_latency_ms=12.0,
        passed=True,
    )
    assert soak.passed
    assert soak.failed_requests == 0


def test_daily_driver_scorecard() -> None:
    card = DailyDriverScorecard(
        wake_success_rate=0.99,
        stt_command_accuracy=0.99,
        android_action_success_rate=1.0,
        overall_classification=ReadinessStatus.READY,
    )
    assert card.overall_classification == ReadinessStatus.READY
    assert card.wake_success_rate == 0.99


def test_production_config_and_rollback_state() -> None:
    cfg = ProductionConfig(environment="production", strict_sandbox=True)
    assert cfg.strict_sandbox

    rollback = RollbackState(
        target_version="1.13.0",
        previous_version="1.14.0",
        snapshot_hash="abc123hash",
        reason="Fault recovery verification",
    )
    assert rollback.target_version == "1.13.0"
    assert not rollback.is_restored
