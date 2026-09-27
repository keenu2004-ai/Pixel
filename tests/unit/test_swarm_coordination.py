"""Unit tests for Swarm Coordination, Leader Election, Failure Detection, and Consensus."""

from packages.contracts.evolution import (
    AgentHeartbeat,
    AgentProposal,
    AgentVote,
    ConsensusStage,
    SwarmAgentIdentity,
    SwarmAgentRole,
    SwarmAgentState,
    VoteDecision,
)
from services.evolution.swarm.coordinator import SwarmCoordinator
from services.evolution.swarm.election import LeaderElection
from services.evolution.swarm.failure_detector import SwarmFailureDetector


def test_leader_election() -> None:
    election = LeaderElection(swarm_id="swarm-01", lease_duration_seconds=10.0)

    c1 = SwarmAgentIdentity(agent_id="agent-01", role=SwarmAgentRole.CODER, trust_level=0.9)
    c2 = SwarmAgentIdentity(agent_id="agent-02", role=SwarmAgentRole.COORDINATOR, trust_level=1.0)
    c3 = SwarmAgentIdentity(agent_id="agent-03", role=SwarmAgentRole.PLANNER, trust_level=0.8)

    candidates = {c1.agent_id: c1, c2.agent_id: c2, c3.agent_id: c3}

    # Elect leader: agent-02 should win (trust 1.0 + role COORDINATOR)
    leader = election.elect_leader(candidates)
    assert leader == "agent-02"
    assert election.current_leader_id == "agent-02"
    assert election.current_lease is not None
    assert election.current_lease.is_active is True

    # Renew lease
    election.record_heartbeat("agent-02")
    renewed = election.renew_lease("agent-02", election.current_epoch)
    assert renewed is True

    # Check wrong epoch renewal fails
    assert election.renew_lease("agent-02", 999) is False

    # Check non-leader renewal fails
    assert election.renew_lease("agent-01", election.current_epoch) is False


def test_failure_detector() -> None:
    detector = SwarmFailureDetector(
        heartbeat_timeout_seconds=5.0,
        degraded_latency_seconds=2.0,
        max_cpu_percent=80.0,
        max_memory_mb=1024.0,
    )

    hb_ok = AgentHeartbeat(
        agent_id="worker-01",
        cpu_usage_percent=20.0,
        memory_mb=256.0,
        status=SwarmAgentState.IDLE,
    )
    state = detector.record_heartbeat(hb_ok)
    assert state == SwarmAgentState.IDLE

    # Overloaded worker -> DEGRADED
    hb_heavy = AgentHeartbeat(
        agent_id="worker-02",
        cpu_usage_percent=90.0,
        memory_mb=512.0,
        status=SwarmAgentState.EXECUTING,
    )
    state = detector.record_heartbeat(hb_heavy)
    assert state == SwarmAgentState.DEGRADED

    # Quarantine agent
    detector.quarantine_agent("worker-02", "Resource abuse")
    assert detector.evaluate_agent_health("worker-02") == SwarmAgentState.QUARANTINED
    detector.unquarantine_agent("worker-02")
    assert detector.evaluate_agent_health("worker-02") == SwarmAgentState.DEGRADED


def test_swarm_coordinator_lifecycle_and_consensus() -> None:
    coordinator = SwarmCoordinator(lease_duration_seconds=20.0)
    session = coordinator.create_swarm(
        swarm_id="swarm-alpha",
        name="Bug Hunting Swarm",
        max_agents=5,
    )
    assert session.is_active is True

    # Register 3 agents
    coord_agent = SwarmAgentIdentity(
        agent_id="agent-coord",
        role=SwarmAgentRole.COORDINATOR,
        trust_level=1.0,
    )
    coder_agent = SwarmAgentIdentity(
        agent_id="agent-coder",
        role=SwarmAgentRole.CODER,
        trust_level=0.9,
    )
    reviewer_agent = SwarmAgentIdentity(
        agent_id="agent-reviewer",
        role=SwarmAgentRole.REVIEWER,
        trust_level=0.95,
    )

    coordinator.register_agent("swarm-alpha", coord_agent)
    coordinator.register_agent("swarm-alpha", coder_agent)
    coordinator.register_agent("swarm-alpha", reviewer_agent)

    # Leader was elected automatically
    active_session = coordinator.get_session("swarm-alpha")
    assert active_session is not None
    assert active_session.leader_id == "agent-coord"

    # Submit proposal
    proposal = AgentProposal(
        proposal_id="prop-101",
        origin_agent_id="agent-coder",
        swarm_id="swarm-alpha",
        title="Refactor database index",
        description="Add composite index on episodic memory",
        action_payload={"table": "episodic_memory", "columns": ["user_id", "timestamp_utc"]},
        risk_tier="REVERSIBLE_WRITE",
    )
    res = coordinator.submit_proposal(proposal)
    assert res.stage == ConsensusStage.ROLE_REVIEW

    # Cast votes
    v1 = AgentVote(
        vote_id="v1",
        proposal_id="prop-101",
        voter_agent_id="agent-coord",
        voter_role=SwarmAgentRole.COORDINATOR,
        decision=VoteDecision.APPROVE,
    )
    v2 = AgentVote(
        vote_id="v2",
        proposal_id="prop-101",
        voter_agent_id="agent-coder",
        voter_role=SwarmAgentRole.CODER,
        decision=VoteDecision.APPROVE,
    )
    v3 = AgentVote(
        vote_id="v3",
        proposal_id="prop-101",
        voter_agent_id="agent-reviewer",
        voter_role=SwarmAgentRole.REVIEWER,
        decision=VoteDecision.APPROVE,
    )

    assert coordinator.vote_on_proposal("swarm-alpha", v1) is True
    assert coordinator.vote_on_proposal("swarm-alpha", v2) is True
    assert coordinator.vote_on_proposal("swarm-alpha", v3) is True

    # Finalize proposal (evaluate votes, L6 Policy Gate, L8 verification)
    final_res = coordinator.finalize_proposal("swarm-alpha", "prop-101")
    assert final_res.is_approved is True
    assert final_res.stage == ConsensusStage.EXECUTED
    assert final_res.policy_verdict == "ALLOW"
    assert final_res.verification_status == "VERIFIED"

    # Terminate swarm
    assert coordinator.terminate_swarm("swarm-alpha") is True
    terminated_sess = coordinator.get_session("swarm-alpha")
    assert terminated_sess is not None
    assert terminated_sess.is_active is False
