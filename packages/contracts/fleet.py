"""PIXEL — Phase 17 Edge AI Swarm Deployment & Fleet Operations Contracts.

Defines canonical contracts and enums for:
1. Fleet Node Identities, Lifecycles, and Trust States.
2. Hardware, Resource, Battery, Thermal, and Network Profiles.
3. Model Capability Profiles, Integrity Hashes, and Distribution Envelopes.
4. Intelligent Routing Decisions, Privacy Classifications, and Explanations.
5. Task Delegation Envelopes, Leases, Checkpoints, and Result Attestations.
6. Fleet Kill Switches, Malicious Node Quarantine, and Autonomous Fleet Missions.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# 1. Fleet Membership, Node States & Data Classifications
# ============================================================================


class FleetNodeState(StrEnum):
    """Lifecycle progression of a node within the fleet."""

    DISCOVERED = "DISCOVERED"
    PAIRING = "PAIRING"
    AUTHENTICATING = "AUTHENTICATING"
    TRUSTED = "TRUSTED"
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    OFFLINE = "OFFLINE"
    REVOKED = "REVOKED"


class FleetDataClassification(StrEnum):
    """Five-tier privacy classification for distributed data envelopes."""

    PUBLIC = "PUBLIC"  # Free to distribute across any online edge worker
    LOW_SENSITIVITY = "LOW_SENSITIVITY"  # General non-personal tasks
    PERSONAL = "PERSONAL"  # User context, preferences, habits
    SENSITIVE = "SENSITIVE"  # Private documents, authenticated sessions
    HIGHLY_SENSITIVE = "HIGHLY_SENSITIVE"  # Passwords, keys, OTPs, biometric data (LOCAL ONLY)


class NetworkCondition(StrEnum):
    """Network connection quality profile of an edge node."""

    EXCELLENT = "EXCELLENT"  # LAN / High-speed Wi-Fi (<10ms RTT)
    GOOD = "GOOD"  # Standard Wi-Fi / 5G (<50ms RTT)
    POOR = "POOR"  # High latency / 4G (>150ms RTT)
    OFFLINE = "OFFLINE"  # No network connectivity


class ThermalState(StrEnum):
    """Thermal throttling status of an edge device."""

    NOMINAL = "NOMINAL"
    WARM = "WARM"
    THROTTLED = "THROTTLED"
    CRITICAL = "CRITICAL"


class FleetCapability(StrEnum):
    """Declared and verified hardware/software capabilities of an edge node."""

    MICROPHONE = "MICROPHONE"
    SPEAKER = "SPEAKER"
    CAMERA = "CAMERA"
    SCREEN = "SCREEN"
    GPU = "GPU"
    NPU = "NPU"
    CPU = "CPU"
    LOCAL_STT = "LOCAL_STT"
    LOCAL_TTS = "LOCAL_TTS"
    LOCAL_VISION = "LOCAL_VISION"
    LOCAL_LLM = "LOCAL_LLM"
    LOCAL_OCR = "LOCAL_OCR"
    BROWSER = "BROWSER"
    TERMINAL = "TERMINAL"
    FILESYSTEM = "FILESYSTEM"
    GIT = "GIT"
    ANDROID = "ANDROID"
    SMART_HOME = "SMART_HOME"
    MEMORY = "MEMORY"
    RAG = "RAG"


# ============================================================================
# 2. Hardware, Resource & Health Profiles
# ============================================================================


class HardwareProfile(BaseModel):
    """Hardware specifications of a physical or virtual edge node."""

    cpu_cores: int = Field(default=4, ge=1)
    cpu_architecture: str = "x86_64"  # x86_64, arm64, aarch64
    has_gpu: bool = False
    gpu_name: str | None = None
    has_npu: bool = False
    total_ram_mb: int = Field(default=8192, ge=512)
    total_vram_mb: int = Field(default=0, ge=0)
    total_storage_mb: int = Field(default=64000, ge=1024)
    os_name: str = "Windows"  # Windows, Linux, Android, Darwin
    accelerator_type: str | None = None  # CUDA, ROCm, Metal, DirectML, NNAPI


class ResourceProfile(BaseModel):
    """Real-time resource utilization and headroom of an edge node."""

    cpu_usage_percent: float = Field(default=10.0, ge=0.0, le=100.0)
    ram_free_mb: int = Field(default=4096, ge=0)
    vram_free_mb: int = Field(default=0, ge=0)
    battery_level_percent: float | None = Field(default=100.0, ge=0.0, le=100.0)
    is_charging: bool = True
    thermal_state: ThermalState = ThermalState.NOMINAL
    network_condition: NetworkCondition = NetworkCondition.EXCELLENT
    rtt_to_authority_ms: float = Field(default=5.0, ge=0.0)
    max_concurrent_tasks: int = Field(default=3, ge=1, le=20)
    active_task_count: int = Field(default=0, ge=0)


class EdgeNodeIdentity(BaseModel):
    """Cryptographic identity and registration profile of an edge node."""

    node_id: str
    node_name: str
    device_type: str = "DESKTOP"  # DESKTOP, PHONE, SERVER, EMBEDDED
    public_key_fingerprint: str
    certificate_serial: str
    is_central_authority: bool = False
    software_version: str = "1.0.0"
    enrolled_at: datetime = Field(default_factory=_utc_now)


class EdgeNode(BaseModel):
    """Canonical edge node representation within the central fleet registry."""

    identity: EdgeNodeIdentity
    state: FleetNodeState = FleetNodeState.ACTIVE
    capabilities: list[FleetCapability] = Field(default_factory=list)
    hardware: HardwareProfile = Field(default_factory=HardwareProfile)
    resources: ResourceProfile = Field(default_factory=ResourceProfile)
    installed_models: list[str] = Field(default_factory=list)  # model_ids
    last_heartbeat: datetime = Field(default_factory=_utc_now)
    quarantine_reason: str | None = None

    def is_available_for_tasks(self) -> bool:
        """Determines if the node is healthy and active for workload placement."""
        if self.state != FleetNodeState.ACTIVE:
            return False
        if self.resources.network_condition == NetworkCondition.OFFLINE:
            return False
        if self.resources.thermal_state == ThermalState.CRITICAL:
            return False
        if (
            self.resources.battery_level_percent is not None
            and self.resources.battery_level_percent < 10.0
            and not self.resources.is_charging
        ):
            return False
        return self.resources.active_task_count < self.resources.max_concurrent_tasks


# ============================================================================
# 3. Model Distribution & Governance Contracts
# ============================================================================


class FleetModelSpec(BaseModel):
    """Metadata specification for a model distributable across fleet edge nodes."""

    model_id: str
    model_name: str
    version: str = "1.0.0"
    architecture: str  # llama, whisper, kokoro, clip, onnx
    quantization: str = "q4_k_m"  # f16, q8_0, q4_k_m, onnx
    size_mb: int = Field(..., ge=1)
    ram_requirement_mb: int = Field(..., ge=128)
    vram_requirement_mb: int = Field(default=0, ge=0)
    supported_capabilities: list[FleetCapability] = Field(default_factory=list)
    sha256_hash: str
    context_window_tokens: int = Field(default=4096, ge=256)
    is_active: bool = True


class ModelDistributionPackage(BaseModel):
    """Signed packaging envelope for distributing a verified model to an edge node."""

    package_id: str = Field(default_factory=_gen_id)
    model_spec: FleetModelSpec
    target_node_id: str
    download_url: str
    sha256_checksum: str
    signed_by_authority: str
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 4. Intelligent Routing & Decision Contracts
# ============================================================================


class RoutingDecision(BaseModel):
    """Structured result of multi-signal task routing calculation."""

    decision_id: str = Field(default_factory=_gen_id)
    task_id: str
    selected_node_id: str
    selected_model_id: str | None = None
    target_capability: FleetCapability
    data_classification: FleetDataClassification
    execution_tier: str = "LOCAL"  # LOCAL, CENTRAL, DISTRIBUTED
    reason: str
    estimated_latency_ms: float
    battery_cost_tier: str = "LOW"  # LOW, MEDIUM, HIGH
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fallback_node_id: str | None = None
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 5. Task Placement, Leases, Checkpoints & Results
# ============================================================================


class TaskLease(BaseModel):
    """Exclusive, time-bounded execution lease granting authority to an edge node."""

    lease_id: str = Field(default_factory=_gen_id)
    task_id: str
    node_id: str
    granted_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
    ttl_seconds: int = 30
    renewed_count: int = 0
    is_active: bool = True

    def is_expired(self) -> bool:
        if not self.is_active:
            return True
        return datetime.now(UTC) > self.expires_at


class DistributedTaskCheckpoint(BaseModel):
    """State checkpoint synchronized between edge worker and central authority."""

    checkpoint_id: str = Field(default_factory=_gen_id)
    task_id: str
    node_id: str
    step_number: int
    state_payload: dict[str, Any] = Field(default_factory=dict)
    tokens_consumed: int = 0
    created_at: datetime = Field(default_factory=_utc_now)


class DelegatedTaskEnvelope(BaseModel):
    """Cryptographically signed delegation payload dispatched to an edge node."""

    task_id: str = Field(default_factory=_gen_id)
    parent_mission_id: str | None = None
    source_node_id: str
    target_node_id: str
    goal_description: str
    capability_required: FleetCapability
    arguments: dict[str, Any] = Field(default_factory=dict)
    data_classification: FleetDataClassification = FleetDataClassification.LOW_SENSITIVITY
    idempotency_key: str = Field(default_factory=_gen_id)
    max_delegation_depth: int = 3
    current_delegation_depth: int = 1
    timeout_ms: int = 10000
    authority_signature: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class WorkerResultAttestation(BaseModel):
    """Attested execution result returned by an edge worker node to central authority."""

    result_id: str = Field(default_factory=_gen_id)
    task_id: str
    node_id: str
    success: bool
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    duration_ms: float = 0.0
    verified_by_l8: bool = False
    worker_signature: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 6. Fleet Kill Switches & Autonomous Mission Contracts
# ============================================================================


class FleetKillSwitchDomain(StrEnum):
    """Emergency kill-switch domains for fleet-wide isolation."""

    ALL_EDGE_EXECUTION = "ALL_EDGE_EXECUTION"
    MODEL_DISTRIBUTION = "MODEL_DISTRIBUTION"
    AUTONOMOUS_DELEGATION = "AUTONOMOUS_DELEGATION"
    REMOTE_INFERENCE = "REMOTE_INFERENCE"
    MEMORY_SYNC = "MEMORY_SYNC"
    VISUAL_SYNC = "VISUAL_SYNC"


class AutonomousFleetMission(BaseModel):
    """Multi-node coordinated mission plan with strict execution bounds."""

    mission_id: str = Field(default_factory=_gen_id)
    user_id: str = "default_user"
    title: str
    goal: str
    allowed_nodes: list[str] = Field(default_factory=list)
    max_delegation_depth: int = 3
    max_retries_per_node: int = 2
    timeout_seconds: float = 60.0
    checkpoints: list[DistributedTaskCheckpoint] = Field(default_factory=list)
    is_completed: bool = False
    is_cancelled: bool = False
    created_at: datetime = Field(default_factory=_utc_now)
