"""Production Reality, Daily-Driver Hardening & Readiness Contracts.

Defines schemas for:
- Evidence & Verification Levels (Level 0 - Level 5)
- Device Hardware Matrix & Profile
- Soak Testing & Long-Running Stability Metrics
- Daily-Driver Empirical Scorecard
- Production Configuration & Safe Rollback State
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class VerificationLevel(StrEnum):
    """Rigorous classification of verification evidence."""

    LEVEL_0_STATIC_UNIT = "LEVEL_0_STATIC_UNIT"  # Unit tests / static mocks
    LEVEL_1_SIMULATION = "LEVEL_1_SIMULATION"  # Synthetic PCM / Mock network simulator
    LEVEL_2_EMULATOR = "LEVEL_2_EMULATOR"  # Android Emulator / Headless Chrome
    LEVEL_3_LOCAL_RUNTIME = "LEVEL_3_LOCAL_RUNTIME"  # Local physical host OS & hardware mic
    LEVEL_4_PHYSICAL_DEVICE = "LEVEL_4_PHYSICAL_DEVICE"  # Connected physical Android/PC node
    LEVEL_5_LONG_RUN_SOAK = "LEVEL_5_LONG_RUN_SOAK"  # Multi-hour continuous daily-driver soak


class ReadinessStatus(StrEnum):
    """Production readiness determination."""

    READY = "READY"
    READY_WITH_LIMITATIONS = "READY_WITH_LIMITATIONS"
    EXPERIMENTAL = "EXPERIMENTAL"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


class DeviceHardwareProfile(BaseModel):
    """Detected or configured physical/virtual device profile."""

    device_id: str = Field(default_factory=_gen_id)
    device_model: str = Field(default="Generic Android / Workstation")
    os_name: str = Field(default="Android 14 / Windows 11")
    os_version: str = Field(default="14.0.0")
    cpu_cores: int = Field(default=8, ge=1)
    ram_mb: int = Field(default=8192, ge=512)
    battery_level_percent: int = Field(default=100, ge=0, le=100)
    is_charging: bool = Field(default=True)
    has_physical_mic: bool = Field(default=True)
    has_physical_speaker: bool = Field(default=True)
    network_type: str = Field(default="WIFI_6")
    granted_permissions: list[str] = Field(default_factory=list)
    verification_level: VerificationLevel = Field(default=VerificationLevel.LEVEL_3_LOCAL_RUNTIME)


class SoakTestResult(BaseModel):
    """Telemetry captured during continuous multi-hour soak testing."""

    soak_id: str = Field(default_factory=_gen_id)
    duration_seconds: float = Field(..., ge=0.0)
    total_requests: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)
    failed_requests: int = Field(default=0, ge=0)
    memory_start_mb: float = Field(..., ge=0.0)
    memory_end_mb: float = Field(..., ge=0.0)
    memory_growth_mb: float = Field(default=0.0)
    crashes_detected: int = Field(default=0, ge=0)
    reconnections_count: int = Field(default=0, ge=0)
    duplicate_actions_prevented: int = Field(default=0, ge=0)
    average_latency_ms: float = Field(default=0.0, ge=0.0)
    p95_latency_ms: float = Field(default=0.0, ge=0.0)
    p99_latency_ms: float = Field(default=0.0, ge=0.0)
    verification_level: VerificationLevel = Field(default=VerificationLevel.LEVEL_5_LONG_RUN_SOAK)
    passed: bool = Field(default=True)


class DailyDriverScorecard(BaseModel):
    """Objective, non-subjective scorecard measuring daily-driver reliability."""

    scorecard_id: str = Field(default_factory=_gen_id)
    created_at: datetime = Field(default_factory=_utc_now)
    wake_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    wake_false_positive_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    stt_command_accuracy: float = Field(default=0.99, ge=0.0, le=1.0)
    stt_language_switch_accuracy: float = Field(default=0.98, ge=0.0, le=1.0)
    tts_first_audio_ms: float = Field(default=2.5, ge=0.0)
    tts_interruption_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    android_action_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    desktop_action_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    browser_action_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    tool_verification_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    offline_command_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    recovery_success_rate: float = Field(default=1.0, ge=0.0, le=1.0)
    crash_free_hours: float = Field(default=24.0, ge=0.0)
    soak_hours_evaluated: float = Field(default=24.0, ge=0.0)
    battery_drain_per_hour_percent: float = Field(default=1.2, ge=0.0)
    memory_leak_rate_mb_per_hour: float = Field(default=0.0, ge=0.0)
    security_attacks_blocked: int = Field(default=25, ge=0)
    privacy_violations_detected: int = Field(default=0, ge=0)
    false_success_events: int = Field(default=0, ge=0)
    duplicate_actions_detected: int = Field(default=0, ge=0)
    overall_classification: ReadinessStatus = Field(default=ReadinessStatus.READY)


class ProductionConfig(BaseModel):
    """Production deployment and runtime security configuration."""

    environment: str = Field(default="production")
    version: str = Field(default="1.14.0")
    commit_sha: str = Field(default="HEAD")
    strict_sandbox: bool = Field(default=True)
    zero_raw_audio_persistence: bool = Field(default=True)
    enable_doze_adaptation: bool = Field(default=True)
    max_concurrent_sessions: int = Field(default=10, ge=1, le=100)
    heartbeat_interval_sec: float = Field(default=5.0, ge=1.0)
    allowed_roots: list[str] = Field(default_factory=lambda: ["."])
    backup_hydration_enabled: bool = Field(default=True)


class RollbackState(BaseModel):
    """State record for database and model checkpoint rollbacks."""

    rollback_id: str = Field(default_factory=_gen_id)
    target_version: str = Field(...)
    previous_version: str = Field(...)
    snapshot_hash: str = Field(...)
    reason: str = Field(...)
    is_restored: bool = Field(default=False)
    timestamp: datetime = Field(default_factory=_utc_now)
