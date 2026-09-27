"""PIXEL — Phase 12 Continuous Autonomous Evolution & Self-Healing Swarms Contracts.

This module defines typed Pydantic models and enums for:
1. Multi-Agent Collaborative Swarms & Hierarchical Consensus.
2. Dynamic Leader Election & Swarm Leases.
3. Continuous Runtime Self-Profiling & Diagnostic Engine.
4. Safe Self-Healing, Change Proposals & Regression Test Generation.
5. Distributed Decentralized Memory Mesh & Conflict Resolution.
6. Privacy-Preserving Model Evolution, Lineage & Differential Privacy.
7. Model Safety Evaluation, Distillation & Governed Promotion.
8. Evolution Governance & Emergency Kill Switches.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ==========================================
# 1. Swarm & Consensus Contracts
# ==========================================


class SwarmAgentRole(StrEnum):
    COORDINATOR = "COORDINATOR"
    PLANNER = "PLANNER"
    RESEARCHER = "RESEARCHER"
    CODER = "CODER"
    TESTER = "TESTER"
    DIAGNOSTICIAN = "DIAGNOSTICIAN"
    REVIEWER = "REVIEWER"
    MEMORY_REPLICATOR = "MEMORY_REPLICATOR"
    MODEL_EVALUATOR = "MODEL_EVALUATOR"
    MODEL_ENGINEER = "MODEL_ENGINEER"
    OBSERVER = "OBSERVER"


class SwarmAgentState(StrEnum):
    INITIALIZING = "INITIALIZING"
    IDLE = "IDLE"
    ASSIGNED = "ASSIGNED"
    EXECUTING = "EXECUTING"
    VOTING = "VOTING"
    DEGRADED = "DEGRADED"
    UNRESPONSIVE = "UNRESPONSIVE"
    FAILED = "FAILED"
    QUARANTINED = "QUARANTINED"
    TERMINATED = "TERMINATED"


class ConsensusStage(StrEnum):
    PROPOSAL = "PROPOSAL"
    ROLE_REVIEW = "ROLE_REVIEW"
    CROSS_AGENT_REVIEW = "CROSS_AGENT_REVIEW"
    VOTING = "VOTING"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"
    CONSENSUS_REJECTED = "CONSENSUS_REJECTED"
    POLICY_EVALUATION = "POLICY_EVALUATION"
    VERIFICATION = "VERIFICATION"
    EXECUTED = "EXECUTED"


class VoteDecision(StrEnum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ABSTAIN = "ABSTAIN"
    REQUEST_REFINEMENT = "REQUEST_REFINEMENT"


class SwarmAgentIdentity(BaseModel):
    agent_id: str
    role: SwarmAgentRole
    capabilities: list[str] = Field(default_factory=list)
    trust_level: float = Field(default=1.0, ge=0.0, le=1.0)
    resource_budget: dict[str, Any] = Field(default_factory=dict)
    lifecycle_state: SwarmAgentState = SwarmAgentState.INITIALIZING
    created_at: str = Field(default_factory=_utc_now_iso)
    provenance: str = "pixel.swarm.core"


class AgentHeartbeat(BaseModel):
    agent_id: str
    epoch: int = 1
    timestamp_utc: str = Field(default_factory=_utc_now_iso)
    cpu_usage_percent: float = Field(default=0.0, ge=0.0)
    memory_mb: float = Field(default=0.0, ge=0.0)
    status: SwarmAgentState = SwarmAgentState.IDLE
    active_task_id: str | None = None


class AgentProposal(BaseModel):
    proposal_id: str
    origin_agent_id: str
    swarm_id: str
    epoch: int = 1
    title: str
    description: str
    action_payload: dict[str, Any] = Field(default_factory=dict)
    risk_tier: str = "REVERSIBLE_WRITE"
    created_at: str = Field(default_factory=_utc_now_iso)


class AgentVote(BaseModel):
    vote_id: str
    proposal_id: str
    voter_agent_id: str
    voter_role: SwarmAgentRole
    decision: VoteDecision
    rationale: str = ""
    signature: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class ConsensusResult(BaseModel):
    proposal_id: str
    swarm_id: str
    epoch: int = 1
    stage: ConsensusStage
    votes_for: int = 0
    votes_against: int = 0
    abstentions: int = 0
    is_approved: bool = False
    policy_verdict: str = "PENDING"
    verification_status: str = "PENDING"
    resolved_at: str = Field(default_factory=_utc_now_iso)


class SwarmLease(BaseModel):
    lease_id: str
    leader_agent_id: str
    epoch: int = 1
    granted_at: str = Field(default_factory=_utc_now_iso)
    expires_at: str
    is_active: bool = True


class SwarmSession(BaseModel):
    swarm_id: str
    name: str
    current_epoch: int = 1
    leader_id: str | None = None
    active_agents: dict[str, SwarmAgentIdentity] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_utc_now_iso)
    max_agents: int = 10
    budget: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True


# ==========================================
# 2. Self-Profiling & Diagnostics Contracts
# ==========================================


class AnomalyType(StrEnum):
    HIGH_LATENCY = "HIGH_LATENCY"
    MEMORY_SPIKE = "MEMORY_SPIKE"
    TASK_FAILURE_SPIKE = "TASK_FAILURE_SPIKE"
    POLICY_DENIAL_SURGE = "POLICY_DENIAL_SURGE"
    MODEL_DRIFT = "MODEL_DRIFT"
    SYNC_LAG = "SYNC_LAG"
    TOOL_TIMEOUT = "TOOL_TIMEOUT"


class AnomalySeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SystemProfileMetric(BaseModel):
    metric_name: str
    timestamp_utc: str = Field(default_factory=_utc_now_iso)
    value: float
    unit: str
    tags: dict[str, str] = Field(default_factory=dict)


class DiagnosticAnomaly(BaseModel):
    anomaly_id: str
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    observed_value: float
    threshold: float
    evidence: dict[str, Any] = Field(default_factory=dict)
    detected_at: str = Field(default_factory=_utc_now_iso)


class RootCauseHypothesis(BaseModel):
    hypothesis_id: str
    anomaly_id: str
    category: str
    explanation: str
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    affected_components: list[str] = Field(default_factory=list)


class RemediationClass(StrEnum):
    RESTART_WORKER = "RESTART_WORKER"
    RENEW_LEASE = "RENEW_LEASE"
    RESTART_SUBPROCESS = "RESTART_SUBPROCESS"
    CLEAR_BOUNDED_CACHE = "CLEAR_BOUNDED_CACHE"
    RETRY_TRANSIENT = "RETRY_TRANSIENT"
    SWITCH_MODEL_REPLICA = "SWITCH_MODEL_REPLICA"
    FAILOVER_DEVICE = "FAILOVER_DEVICE"
    RESCHEDULE_TASK = "RESCHEDULE_TASK"
    PROPOSE_CODE_PATCH = "PROPOSE_CODE_PATCH"
    PROPOSE_CONFIG_CHANGE = "PROPOSE_CONFIG_CHANGE"


class RemediationProposal(BaseModel):
    proposal_id: str
    anomaly_id: str
    hypothesis_id: str
    remediation_class: RemediationClass
    is_automatic_allowed: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_class: str = "REVERSIBLE_WRITE"
    status: str = "PENDING"
    created_at: str = Field(default_factory=_utc_now_iso)


# ==========================================
# 3. Change Proposals & Self-Healing Contracts
# ==========================================


class ChangeProposalState(StrEnum):
    PROPOSED = "PROPOSED"
    ANALYZED = "ANALYZED"
    TESTING = "TESTING"
    VERIFIED = "VERIFIED"
    CANARY = "CANARY"
    APPROVED = "APPROVED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    ROLLED_BACK = "ROLLED_BACK"
    EXPIRED = "EXPIRED"


class ChangeType(StrEnum):
    CODE_PATCH = "CODE_PATCH"
    CONFIG_UPDATE = "CONFIG_UPDATE"
    MODEL_ADAPTATION = "MODEL_ADAPTATION"
    MEMORY_SCHEMA_MIGRATION = "MEMORY_SCHEMA_MIGRATION"


class ChangeProposal(BaseModel):
    proposal_id: str
    originating_agent_id: str
    swarm_id: str
    change_type: ChangeType
    state: ChangeProposalState = ChangeProposalState.PROPOSED
    title: str
    reason: str
    diff_content: str = ""
    regression_test_code: str = ""
    expected_outcome: str = ""
    rollback_plan: str = ""
    canary_percentage: int = 0
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


class GeneratedRegressionTest(BaseModel):
    test_id: str
    target_module: str
    test_code: str
    ast_valid: bool = True
    safety_checked: bool = True
    created_at: str = Field(default_factory=_utc_now_iso)


# ==========================================
# 4. Distributed Memory Mesh Contracts
# ==========================================


class MeshSyncState(StrEnum):
    NO_CONFLICT = "NO_CONFLICT"
    CONVERGED = "CONVERGED"
    CONFLICT = "CONFLICT"
    QUARANTINED = "QUARANTINED"
    MANUAL_REVIEW = "MANUAL_REVIEW"


class ReplicatedMemoryItem(BaseModel):
    memory_id: str
    owner_user_id: str
    version: int = 1
    vector_clock: dict[str, int] = Field(default_factory=dict)
    origin_node_id: str
    content_payload: dict[str, Any] = Field(default_factory=dict)
    sensitivity_class: str = "CONFIDENTIAL"
    is_tombstone: bool = False
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: str = Field(default_factory=_utc_now_iso)


class MemoryReplicationEnvelope(BaseModel):
    envelope_id: str
    origin_node_id: str
    target_node_id: str
    items: list[ReplicatedMemoryItem] = Field(default_factory=list)
    timestamp_utc: str = Field(default_factory=_utc_now_iso)
    signature: str = ""


class ConflictRecord(BaseModel):
    conflict_id: str
    memory_id: str
    local_version: int
    remote_version: int
    local_item: dict[str, Any] = Field(default_factory=dict)
    remote_item: dict[str, Any] = Field(default_factory=dict)
    resolution_state: MeshSyncState = MeshSyncState.CONFLICT
    resolved_item: dict[str, Any] | None = None
    detected_at: str = Field(default_factory=_utc_now_iso)


# ==========================================
# 5. Model Evolution & Distillation Contracts
# ==========================================


class EvolutionModelLifecycleState(StrEnum):
    DISCOVERED = "DISCOVERED"
    EVALUATED = "EVALUATED"
    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"
    CANARY = "CANARY"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    DEPRECATED = "DEPRECATED"
    ROLLED_BACK = "ROLLED_BACK"
    REVOKED = "REVOKED"


class TrainingConsentStatus(StrEnum):
    CONSENT_GRANTED = "CONSENT_GRANTED"
    CONSENT_DENIED = "CONSENT_DENIED"
    CONSENT_REVOKED = "CONSENT_REVOKED"
    EXPIRED = "EXPIRED"


class TrainingDataLineage(BaseModel):
    lineage_id: str
    interaction_id: str
    user_id: str
    consent_status: TrainingConsentStatus = TrainingConsentStatus.CONSENT_GRANTED
    pii_scrubbed: bool = True
    source_timestamp: str = Field(default_factory=_utc_now_iso)
    dataset_revision: str = "v1"
    created_at: str = Field(default_factory=_utc_now_iso)


class DifferentialPrivacyBudget(BaseModel):
    budget_id: str
    epsilon_max: float = 1.0
    epsilon_consumed: float = 0.0
    delta_max: float = 1e-5
    delta_consumed: float = 0.0
    mechanism: str = "GAUSSIAN"
    last_updated_at: str = Field(default_factory=_utc_now_iso)


class ModelEvaluationMetric(BaseModel):
    evaluation_id: str
    model_id: str
    model_family: str
    benchmark_accuracy: float = 0.0
    hallucination_score: float = 0.0
    policy_compliance_rate: float = 1.0
    injection_resistance_score: float = 1.0
    latency_p95_ms: float = 0.0
    memory_vram_mb: float = 0.0
    is_regression_free: bool = True
    evaluated_at: str = Field(default_factory=_utc_now_iso)


class DistillationRun(BaseModel):
    distillation_id: str
    teacher_model_id: str
    student_model_id: str
    dataset_revision: str
    loss_final: float = 0.0
    accuracy_retention: float = 0.0
    compression_ratio: float = 1.0
    status: str = "COMPLETED"
    created_at: str = Field(default_factory=_utc_now_iso)


class ModelPromotionDecision(BaseModel):
    promotion_id: str
    candidate_model_id: str
    baseline_model_id: str
    evaluation_id: str
    is_promoted: bool = False
    canary_traffic_percent: int = 0
    promoted_by: str = "evolution.governor"
    decision_rationale: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ==========================================
# 6. Governance & Kill Switch Contracts
# ==========================================


class KillSwitchDomain(StrEnum):
    ALL_SWARMS = "ALL_SWARMS"
    AUTONOMOUS_REMEDIATION = "AUTONOMOUS_REMEDIATION"
    MODEL_PROMOTION = "MODEL_PROMOTION"
    CODE_PROMOTION = "CODE_PROMOTION"
    MEMORY_REPLICATION = "MEMORY_REPLICATION"
    TRAINING_PIPELINE = "TRAINING_PIPELINE"


class KillSwitchStatus(BaseModel):
    domain: KillSwitchDomain
    is_active: bool = False
    tripped_at: str | None = None
    tripped_by: str | None = None
    reason: str | None = None


class EvolutionPolicy(BaseModel):
    policy_id: str = "default_policy"
    allow_automatic_remediation: bool = True
    max_daily_proposals: int = 50
    min_consensus_votes: int = 2
    canary_min_duration_seconds: int = 300
    require_human_approval_for_code: bool = True
