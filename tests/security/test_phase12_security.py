"""Hostile Security Red-Team Test Suite for Phase 12 Continuous Autonomous Evolution & Swarms."""

import tempfile

import pytest

from packages.contracts.evolution import (
    AgentProposal,
    AgentVote,
    ChangeProposalState,
    KillSwitchDomain,
    RemediationClass,
    RemediationProposal,
    ReplicatedMemoryItem,
    SwarmAgentIdentity,
    SwarmAgentRole,
    VoteDecision,
)
from services.evolution.governance.governor import EvolutionGovernor
from services.evolution.governance.kill_switches import KillSwitchSystem
from services.evolution.healing.orchestrator import SelfHealingOrchestrator
from services.evolution.healing.proposals import ChangeProposalManager
from services.evolution.healing.regression_generator import RegressionTestGenerator
from services.evolution.memory_mesh.conflict_resolver import MemoryConflictResolver
from services.evolution.models.evaluator import ModelSafetyEvaluator
from services.evolution.models.registry import EvolutionModelRegistry
from services.evolution.swarm.coordinator import SwarmCoordinator
from services.evolution.swarm.election import LeaderElection


def test_swarm_attack_stale_leader_rejection() -> None:
    election = LeaderElection(swarm_id="swarm-hack", lease_duration_seconds=0.1)
    cand = SwarmAgentIdentity(
        agent_id="leader-01", role=SwarmAgentRole.COORDINATOR, trust_level=1.0
    )
    election.elect_leader({cand.agent_id: cand})

    assert election.current_leader_id == "leader-01"

    # Expire lease by not recording heartbeat
    import time

    time.sleep(0.15)

    assert election.is_leader_alive() is False


def test_swarm_attack_non_member_proposal_rejected() -> None:
    coordinator = SwarmCoordinator()
    coordinator.create_swarm("swarm-sec", "Security Swarm")

    # Outside agent attempts to submit proposal
    prop = AgentProposal(
        proposal_id="prop-rogue",
        origin_agent_id="rogue-agent",
        swarm_id="swarm-sec",
        title="Malicious payload",
        description="Attempting to hijack swarm",
    )

    with pytest.raises(PermissionError, match="is not a member"):
        coordinator.submit_proposal(prop)


def test_swarm_attack_double_voting_blocked() -> None:
    coordinator = SwarmCoordinator()
    coordinator.create_swarm("swarm-sec", "Security Swarm")
    c1 = SwarmAgentIdentity(agent_id="agent-1", role=SwarmAgentRole.COORDINATOR, trust_level=1.0)
    c2 = SwarmAgentIdentity(agent_id="agent-2", role=SwarmAgentRole.CODER, trust_level=1.0)
    coordinator.register_agent("swarm-sec", c1)
    coordinator.register_agent("swarm-sec", c2)

    prop = AgentProposal(
        proposal_id="prop-legit",
        origin_agent_id="agent-1",
        swarm_id="swarm-sec",
        title="Legitimate task",
        description="Normal proposal",
    )
    coordinator.submit_proposal(prop)

    vote1 = AgentVote(
        vote_id="v1",
        proposal_id="prop-legit",
        voter_agent_id="agent-2",
        voter_role=SwarmAgentRole.CODER,
        decision=VoteDecision.APPROVE,
    )
    assert coordinator.vote_on_proposal("swarm-sec", vote1) is True

    # Double vote attempt
    vote2 = AgentVote(
        vote_id="v2",
        proposal_id="prop-legit",
        voter_agent_id="agent-2",
        voter_role=SwarmAgentRole.CODER,
        decision=VoteDecision.APPROVE,
    )
    assert coordinator.vote_on_proposal("swarm-sec", vote2) is False


def test_regression_generator_blocks_sandbox_escape() -> None:
    gen = RegressionTestGenerator()

    # Attempt to bypass L6 policy inside generated test
    hostile_code = """
import pytest
def test_bypass():
    policy_gate = None
    assert True
"""
    valid, is_safe, violations = gen.validate_test_safety(hostile_code)
    assert is_safe is False
    assert any("Forbidden attempt to alter policy" in v for v in violations)


def test_self_healing_blocks_unauthorized_code_modification() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        mgr = ChangeProposalManager(db_path=f"{tmp_dir}/prop.db")
        orchestrator = SelfHealingOrchestrator(proposal_manager=mgr)

        # Non-allowlisted remediation proposal (CODE_PATCH without human approval)
        prop = RemediationProposal(
            proposal_id="rem-code-1",
            anomaly_id="anom-1",
            hypothesis_id="hypo-1",
            remediation_class=RemediationClass.PROPOSE_CODE_PATCH,
            is_automatic_allowed=False,
            parameters={"patch": "def foo(): pass"},
        )

        change = orchestrator.process_remediation(prop)
        # Must not automatically promote!
        assert change.state == ChangeProposalState.ANALYZED
        assert change.canary_percentage == 0


def test_memory_mesh_cross_user_boundary_isolation() -> None:
    resolver = MemoryConflictResolver()
    item_user_a = ReplicatedMemoryItem(
        memory_id="mem-1",
        owner_user_id="user-a",
        version=1,
        vector_clock={"node-1": 1},
        origin_node_id="node-1",
        content_payload={"secret": "user_a_data"},
    )
    item_user_b = ReplicatedMemoryItem(
        memory_id="mem-1",
        owner_user_id="user-b",
        version=1,
        vector_clock={"node-2": 1},
        origin_node_id="node-2",
        content_payload={"secret": "user_b_data"},
    )

    state, item, conflict = resolver.resolve(item_user_a, item_user_b)
    # Must be quarantined
    assert state.value == "QUARANTINED"
    assert conflict is not None


def test_model_evolution_blocks_policy_violating_model() -> None:
    evaluator = ModelSafetyEvaluator()

    # Model with 95% accuracy but 90% policy compliance (violates 100% policy invariant)
    eval_result = evaluator.evaluate_model(
        model_id="rogue-model-v1",
        model_family="llama",
        benchmark_accuracy=0.95,
        hallucination_score=0.01,
        policy_compliance_rate=0.90,  # Fails!
        injection_resistance_score=0.99,
        latency_p95_ms=100.0,
        memory_vram_mb=1024.0,
    )
    assert eval_result.is_regression_free is False

    registry = EvolutionModelRegistry(evaluator=evaluator)
    registry.register_model("rogue-model-v1", "llama", "hash_mock")
    registry.link_evaluation("rogue-model-v1", eval_result)

    # Attempt to promote -> Fails
    assert registry.promote_to_candidate("rogue-model-v1") is False


def test_governor_killswitch_enforcement() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        ks = KillSwitchSystem(db_path=f"{tmp_dir}/kill.db")
        governor = EvolutionGovernor(kill_switch_system=ks)

        # Trip memory replication killswitch
        ks.trip_switch(KillSwitchDomain.MEMORY_REPLICATION, reason="Data breach suspected")
        assert governor.can_replicate_memory() is False

        # Trip model promotion killswitch
        ks.trip_switch(KillSwitchDomain.MODEL_PROMOTION, reason="Hallucination surge")
        assert governor.can_promote_model() is False
