"""Unit tests for Phase 12 Continuous Autonomous Evolution & Self-Healing Swarms contracts."""

from packages.contracts.evolution import (
    AgentHeartbeat,
    AgentProposal,
    AgentVote,
    AnomalySeverity,
    AnomalyType,
    ChangeProposal,
    ChangeProposalState,
    ChangeType,
    ConflictRecord,
    ConsensusResult,
    ConsensusStage,
    DiagnosticAnomaly,
    DifferentialPrivacyBudget,
    DistillationRun,
    EvolutionPolicy,
    GeneratedRegressionTest,
    KillSwitchDomain,
    KillSwitchStatus,
    MemoryReplicationEnvelope,
    MeshSyncState,
    ModelEvaluationMetric,
    ModelPromotionDecision,
    RemediationClass,
    RemediationProposal,
    ReplicatedMemoryItem,
    RootCauseHypothesis,
    SwarmAgentIdentity,
    SwarmAgentRole,
    SwarmAgentState,
    SwarmLease,
    SwarmSession,
    SystemProfileMetric,
    TrainingConsentStatus,
    TrainingDataLineage,
    VoteDecision,
)


def test_swarm_contracts() -> None:
    identity = SwarmAgentIdentity(
        agent_id="agent-coord-01",
        role=SwarmAgentRole.COORDINATOR,
        capabilities=["SWARM_COORDINATION", "LEASE_MANAGEMENT"],
        trust_level=1.0,
    )
    assert identity.agent_id == "agent-coord-01"
    assert identity.role == SwarmAgentRole.COORDINATOR
    assert identity.lifecycle_state == SwarmAgentState.INITIALIZING

    heartbeat = AgentHeartbeat(
        agent_id="agent-coord-01",
        epoch=1,
        cpu_usage_percent=12.5,
        memory_mb=256.0,
        status=SwarmAgentState.IDLE,
    )
    assert heartbeat.cpu_usage_percent == 12.5
    assert heartbeat.epoch == 1

    proposal = AgentProposal(
        proposal_id="prop-001",
        origin_agent_id="agent-planner-01",
        swarm_id="swarm-alpha",
        epoch=1,
        title="Scale workers for background memory indexing",
        description="Increase worker concurrency from 2 to 4",
        action_payload={"target_concurrency": 4},
    )
    assert proposal.title.startswith("Scale")

    vote = AgentVote(
        vote_id="vote-001",
        proposal_id="prop-001",
        voter_agent_id="agent-reviewer-01",
        voter_role=SwarmAgentRole.REVIEWER,
        decision=VoteDecision.APPROVE,
        rationale="Within resource budgets",
    )
    assert vote.decision == VoteDecision.APPROVE

    consensus = ConsensusResult(
        proposal_id="prop-001",
        swarm_id="swarm-alpha",
        epoch=1,
        stage=ConsensusStage.CONSENSUS_REACHED,
        votes_for=3,
        votes_against=0,
        abstentions=0,
        is_approved=True,
    )
    assert consensus.is_approved is True

    lease = SwarmLease(
        lease_id="lease-001",
        leader_agent_id="agent-coord-01",
        epoch=1,
        expires_at="2026-12-31T23:59:59Z",
    )
    assert lease.is_active is True

    session = SwarmSession(
        swarm_id="swarm-alpha",
        name="Memory Optimization Swarm",
        current_epoch=1,
        leader_id="agent-coord-01",
        active_agents={"agent-coord-01": identity},
    )
    assert session.name == "Memory Optimization Swarm"


def test_diagnostics_contracts() -> None:
    metric = SystemProfileMetric(
        metric_name="pixel.agent.step_latency_ms",
        value=145.0,
        unit="ms",
        tags={"component": "agent_runtime"},
    )
    assert metric.value == 145.0

    anomaly = DiagnosticAnomaly(
        anomaly_id="anom-001",
        anomaly_type=AnomalyType.HIGH_LATENCY,
        severity=AnomalySeverity.HIGH,
        observed_value=1250.0,
        threshold=500.0,
        evidence={"endpoint": "/api/v1/query"},
    )
    assert anomaly.severity == AnomalySeverity.HIGH

    hypothesis = RootCauseHypothesis(
        hypothesis_id="hypo-001",
        anomaly_id="anom-001",
        category="DATABASE_LOCK",
        explanation="High lock contention during SQLite memory sync",
        confidence=0.85,
        affected_components=["sqlite_memory_store"],
    )
    assert hypothesis.confidence == 0.85

    remediation = RemediationProposal(
        proposal_id="rem-001",
        anomaly_id="anom-001",
        hypothesis_id="hypo-001",
        remediation_class=RemediationClass.CLEAR_BOUNDED_CACHE,
        is_automatic_allowed=True,
        parameters={"cache_name": "query_cache"},
    )
    assert remediation.is_automatic_allowed is True


def test_change_proposal_and_regression_contracts() -> None:
    change = ChangeProposal(
        proposal_id="chg-001",
        originating_agent_id="agent-coder-01",
        swarm_id="swarm-alpha",
        change_type=ChangeType.CONFIG_UPDATE,
        state=ChangeProposalState.PROPOSED,
        title="Adjust database busy timeout",
        reason="Prevent sqlite lock timeout",
        diff_content="timeout: 5.0 -> 10.0",
        rollback_plan="Revert timeout to 5.0",
    )
    assert change.state == ChangeProposalState.PROPOSED

    reg_test = GeneratedRegressionTest(
        test_id="reg-001",
        target_module="services.memory.stores.sqlite_store",
        test_code="def test_busy_timeout(): assert True",
        ast_valid=True,
        safety_checked=True,
    )
    assert reg_test.ast_valid is True


def test_memory_mesh_contracts() -> None:
    item = ReplicatedMemoryItem(
        memory_id="mem-fact-001",
        owner_user_id="user-vaibhav",
        version=1,
        vector_clock={"node-pc": 1, "node-android": 0},
        origin_node_id="node-pc",
        content_payload={"fact": "Prefers dark mode", "category": "preferences"},
    )
    assert item.memory_id == "mem-fact-001"
    assert item.is_tombstone is False

    envelope = MemoryReplicationEnvelope(
        envelope_id="env-001",
        origin_node_id="node-pc",
        target_node_id="node-android",
        items=[item],
    )
    assert len(envelope.items) == 1

    conflict = ConflictRecord(
        conflict_id="conf-001",
        memory_id="mem-fact-001",
        local_version=2,
        remote_version=2,
        local_item={"fact": "Prefers dark mode"},
        remote_item={"fact": "Prefers light mode"},
        resolution_state=MeshSyncState.CONFLICT,
    )
    assert conflict.resolution_state == MeshSyncState.CONFLICT


def test_model_evolution_and_governance_contracts() -> None:
    lineage = TrainingDataLineage(
        lineage_id="lin-001",
        interaction_id="int-123",
        user_id="user-vaibhav",
        consent_status=TrainingConsentStatus.CONSENT_GRANTED,
        pii_scrubbed=True,
    )
    assert lineage.consent_status == TrainingConsentStatus.CONSENT_GRANTED

    dp = DifferentialPrivacyBudget(
        budget_id="dp-001",
        epsilon_max=2.0,
        epsilon_consumed=0.5,
        delta_max=1e-5,
    )
    assert dp.epsilon_consumed == 0.5

    eval_metric = ModelEvaluationMetric(
        evaluation_id="eval-001",
        model_id="qwen2.5-0.5b-adapted-v2",
        model_family="qwen",
        benchmark_accuracy=0.92,
        hallucination_score=0.03,
        policy_compliance_rate=1.0,
        is_regression_free=True,
    )
    assert eval_metric.is_regression_free is True

    distill = DistillationRun(
        distillation_id="dist-001",
        teacher_model_id="llama-3.2-3b",
        student_model_id="llama-3.2-1b",
        dataset_revision="v2",
        loss_final=0.14,
        accuracy_retention=0.96,
        compression_ratio=3.0,
    )
    assert distill.compression_ratio == 3.0

    promo = ModelPromotionDecision(
        promotion_id="prm-001",
        candidate_model_id="llama-3.2-1b-distilled",
        baseline_model_id="llama-3.2-1b-base",
        evaluation_id="eval-001",
        is_promoted=True,
        canary_traffic_percent=10,
    )
    assert promo.is_promoted is True

    kill = KillSwitchStatus(
        domain=KillSwitchDomain.AUTONOMOUS_REMEDIATION,
        is_active=False,
    )
    assert kill.is_active is False

    policy = EvolutionPolicy()
    assert policy.allow_automatic_remediation is True
