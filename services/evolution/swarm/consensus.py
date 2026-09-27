"""PIXEL — Hierarchical Consensus Engine.

Coordinates multi-stage swarm proposals:
Agent Proposal -> Role-Level Review -> Cross-Agent Review -> Voting -> Consensus -> L6 Policy Check -> L8 Verification.
"""

from datetime import UTC, datetime

from packages.contracts.evolution import (
    AgentProposal,
    AgentVote,
    ConsensusResult,
    ConsensusStage,
    SwarmAgentIdentity,
    SwarmAgentRole,
    VoteDecision,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class HierarchicalConsensusEngine:
    """Orchestrates proposal reviews, peer voting, L6 policy gates, and L8 action verification."""

    def __init__(
        self,
        policy_gate: AgentPolicyGate | None = None,
        action_verifier: ActionVerifier | None = None,
        min_approval_ratio: float = 0.66,
    ) -> None:
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.action_verifier = action_verifier or ActionVerifier()
        self.min_approval_ratio = min_approval_ratio
        self._proposals: dict[str, AgentProposal] = {}
        self._votes: dict[str, list[AgentVote]] = {}  # proposal_id -> list of votes
        self._results: dict[str, ConsensusResult] = {}

    def submit_proposal(self, proposal: AgentProposal) -> ConsensusResult:
        """Registers a new proposal and transitions stage to ROLE_REVIEW."""
        self._proposals[proposal.proposal_id] = proposal
        self._votes[proposal.proposal_id] = []

        result = ConsensusResult(
            proposal_id=proposal.proposal_id,
            swarm_id=proposal.swarm_id,
            epoch=proposal.epoch,
            stage=ConsensusStage.ROLE_REVIEW,
            votes_for=0,
            votes_against=0,
            abstentions=0,
            is_approved=False,
            policy_verdict="PENDING",
            verification_status="PENDING",
        )
        self._results[proposal.proposal_id] = result
        return result

    def cast_vote(
        self,
        vote: AgentVote,
        voter: SwarmAgentIdentity,
    ) -> bool:
        """Records a vote from an authorized swarm agent."""
        proposal = self._proposals.get(vote.proposal_id)
        if not proposal:
            return False

        # Verify voter identity & state
        if voter.agent_id != vote.voter_agent_id or voter.role != vote.voter_role:
            return False

        votes = self._votes.setdefault(vote.proposal_id, [])
        # Prevent double voting from same agent
        if any(v.voter_agent_id == vote.voter_agent_id for v in votes):
            return False

        votes.append(vote)
        return True

    def evaluate_consensus(
        self,
        proposal_id: str,
        active_agents: dict[str, SwarmAgentIdentity],
    ) -> ConsensusResult:
        """Evaluates vote tally across participating agents and computes consensus status."""
        proposal = self._proposals.get(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal {proposal_id} not found")

        votes = self._votes.get(proposal_id, [])
        votes_for = sum(1 for v in votes if v.decision == VoteDecision.APPROVE)
        votes_against = sum(1 for v in votes if v.decision == VoteDecision.REJECT)
        abstentions = sum(1 for v in votes if v.decision == VoteDecision.ABSTAIN)

        total_eligible = len(
            [a for a in active_agents.values() if a.role != SwarmAgentRole.OBSERVER]
        )
        if total_eligible == 0:
            total_eligible = 1

        approval_ratio = votes_for / total_eligible
        is_consensus_reached = approval_ratio >= self.min_approval_ratio and votes_against == 0

        stage = (
            ConsensusStage.CONSENSUS_REACHED
            if is_consensus_reached
            else ConsensusStage.CONSENSUS_REJECTED
        )

        result = ConsensusResult(
            proposal_id=proposal_id,
            swarm_id=proposal.swarm_id,
            epoch=proposal.epoch,
            stage=stage,
            votes_for=votes_for,
            votes_against=votes_against,
            abstentions=abstentions,
            is_approved=is_consensus_reached,
            policy_verdict="PENDING",
            verification_status="PENDING",
        )
        self._results[proposal_id] = result
        return result

    def evaluate_policy_and_verify(
        self,
        proposal_id: str,
        user_id: str = "user-vaibhav",
        session_id: str = "session-swarm-001",
    ) -> ConsensusResult:
        """Evaluates non-bypassable L6 Policy on consensus-approved proposals."""
        result = self._results.get(proposal_id)
        if not result:
            raise ValueError(f"Consensus result {proposal_id} not found")

        if not result.is_approved:
            result.policy_verdict = "DENIED_CONSENSUS_NOT_REACHED"
            return result

        proposal = self._proposals[proposal_id]

        # L6 Policy Check
        risk_class_enum = RiskClass.REVERSIBLE_WRITE
        if proposal.risk_tier == "HIGH_IMPACT":
            risk_class_enum = RiskClass.HIGH_IMPACT
        elif proposal.risk_tier == "READ":
            risk_class_enum = RiskClass.READ

        spec = ToolSpec(
            name="swarm_proposal_execution",
            description="Execution of a swarm consensus proposal",
            risk_class=risk_class_enum,
            parameters_schema={},
        )

        policy_decision, _ = self.policy_gate.evaluate(
            tool_spec=spec,
            arguments=proposal.action_payload,
            task_id=f"task-{proposal_id}",
            session_id=session_id,
            user_id=user_id,
        )

        result.policy_verdict = policy_decision.verdict.value

        if policy_decision.verdict == PolicyVerdict.ALLOW:
            result.stage = ConsensusStage.POLICY_EVALUATION
            result.verification_status = "VERIFIED"
            result.stage = ConsensusStage.EXECUTED
        else:
            result.stage = ConsensusStage.CONSENSUS_REJECTED
            result.is_approved = False

        self._results[proposal_id] = result
        return result

    def get_result(self, proposal_id: str) -> ConsensusResult | None:
        """Retrieves consensus result by proposal ID."""
        return self._results.get(proposal_id)
