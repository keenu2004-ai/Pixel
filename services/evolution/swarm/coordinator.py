"""PIXEL — Swarm Coordinator.

Coordinates multi-agent swarm sessions, lifecycle management, role delegation,
leader election, health oversight, and policy-governed consensus execution.
"""

from datetime import UTC, datetime

from packages.contracts.evolution import (
    AgentHeartbeat,
    AgentProposal,
    AgentVote,
    ConsensusResult,
    SwarmAgentIdentity,
    SwarmAgentState,
    SwarmSession,
)
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier
from services.evolution.swarm.consensus import HierarchicalConsensusEngine
from services.evolution.swarm.election import LeaderElection
from services.evolution.swarm.failure_detector import SwarmFailureDetector


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class SwarmCoordinator:
    """Manages active swarms, leader leases, failure recovery, and consensus."""

    def __init__(
        self,
        policy_gate: AgentPolicyGate | None = None,
        action_verifier: ActionVerifier | None = None,
        lease_duration_seconds: float = 30.0,
    ) -> None:
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.action_verifier = action_verifier or ActionVerifier()
        self.lease_duration_seconds = lease_duration_seconds
        self._sessions: dict[str, SwarmSession] = {}
        self._elections: dict[str, LeaderElection] = {}
        self._failure_detectors: dict[str, SwarmFailureDetector] = {}
        self._consensus_engines: dict[str, HierarchicalConsensusEngine] = {}

    def create_swarm(
        self,
        swarm_id: str,
        name: str,
        max_agents: int = 10,
        budget: dict[str, int] | None = None,
    ) -> SwarmSession:
        """Initializes a new collaborative swarm session."""
        session = SwarmSession(
            swarm_id=swarm_id,
            name=name,
            max_agents=max_agents,
            budget=budget or {"max_steps": 50, "max_tokens": 100000, "max_proposals": 20},
            created_at=_utc_now_iso(),
            is_active=True,
        )
        self._sessions[swarm_id] = session
        self._elections[swarm_id] = LeaderElection(swarm_id, self.lease_duration_seconds)
        self._failure_detectors[swarm_id] = SwarmFailureDetector()
        self._consensus_engines[swarm_id] = HierarchicalConsensusEngine(
            policy_gate=self.policy_gate,
            action_verifier=self.action_verifier,
        )
        return session

    def register_agent(
        self,
        swarm_id: str,
        identity: SwarmAgentIdentity,
    ) -> bool:
        """Registers an agent into a swarm session."""
        session = self._sessions.get(swarm_id)
        if not session or not session.is_active:
            return False

        if len(session.active_agents) >= session.max_agents:
            return False

        identity.lifecycle_state = SwarmAgentState.IDLE
        session.active_agents[identity.agent_id] = identity

        # Record initial heartbeat in election and detector
        hb = AgentHeartbeat(agent_id=identity.agent_id, epoch=session.current_epoch)
        self._elections[swarm_id].record_heartbeat(identity.agent_id)
        self._failure_detectors[swarm_id].record_heartbeat(hb)

        # Trigger leader election if no leader is currently elected
        if not session.leader_id or not self._elections[swarm_id].is_leader_alive():
            leader_id = self._elections[swarm_id].elect_leader(session.active_agents)
            session.leader_id = leader_id
            session.current_epoch = self._elections[swarm_id].current_epoch

        return True

    def process_heartbeat(self, swarm_id: str, heartbeat: AgentHeartbeat) -> SwarmAgentState:
        """Processes an agent heartbeat and checks leader validity."""
        session = self._sessions.get(swarm_id)
        if not session:
            return SwarmAgentState.TERMINATED

        self._elections[swarm_id].record_heartbeat(heartbeat.agent_id)
        state = self._failure_detectors[swarm_id].record_heartbeat(heartbeat)

        agent = session.active_agents.get(heartbeat.agent_id)
        if agent:
            agent.lifecycle_state = state

        # Check if leader has died
        if not self._elections[swarm_id].is_leader_alive():
            new_leader = self._elections[swarm_id].elect_leader(session.active_agents)
            session.leader_id = new_leader
            session.current_epoch = self._elections[swarm_id].current_epoch

        return state

    def submit_proposal(self, proposal: AgentProposal) -> ConsensusResult:
        """Submits an agent proposal to the swarm's consensus engine."""
        session = self._sessions.get(proposal.swarm_id)
        if not session or not session.is_active:
            raise ValueError(f"Swarm {proposal.swarm_id} is not active")

        # Verify proposer is active in swarm
        if proposal.origin_agent_id not in session.active_agents:
            raise PermissionError(
                f"Agent {proposal.origin_agent_id} is not a member of {proposal.swarm_id}"
            )

        engine = self._consensus_engines[proposal.swarm_id]
        return engine.submit_proposal(proposal)

    def vote_on_proposal(self, swarm_id: str, vote: AgentVote) -> bool:
        """Casts a vote on a proposal on behalf of a registered agent."""
        session = self._sessions.get(swarm_id)
        if not session or not session.is_active:
            return False

        voter = session.active_agents.get(vote.voter_agent_id)
        if not voter:
            return False

        engine = self._consensus_engines[swarm_id]
        return engine.cast_vote(vote, voter)

    def finalize_proposal(
        self,
        swarm_id: str,
        proposal_id: str,
        user_id: str = "user-vaibhav",
    ) -> ConsensusResult:
        """Evaluates tally, checks L6 policy, and verifies L8 execution."""
        session = self._sessions.get(swarm_id)
        if not session or not session.is_active:
            raise ValueError(f"Swarm {swarm_id} is not active")

        engine = self._consensus_engines[swarm_id]
        # Step 1: Consensus tally
        consensus = engine.evaluate_consensus(proposal_id, session.active_agents)
        if not consensus.is_approved:
            return consensus

        # Step 2: Policy and L8 verification
        return engine.evaluate_policy_and_verify(proposal_id, user_id=user_id)

    def get_session(self, swarm_id: str) -> SwarmSession | None:
        """Retrieves swarm session state."""
        return self._sessions.get(swarm_id)

    def terminate_swarm(self, swarm_id: str, reason: str = "completed") -> bool:
        """Terminates an active swarm session."""
        session = self._sessions.get(swarm_id)
        if not session:
            return False

        session.is_active = False
        for agent in session.active_agents.values():
            agent.lifecycle_state = SwarmAgentState.TERMINATED
        if swarm_id in self._elections:
            self._elections[swarm_id].revoke_leadership(reason)
        return True
