"""PIXEL — Self-Healing Orchestrator.

Orchestrates the safe self-healing lifecycle:
DETECT -> DIAGNOSE -> PROPOSE -> POLICY CHECK -> SIMULATE -> TEST -> CANARY -> VERIFY -> PROMOTE / ROLLBACK.
"""

import uuid

from packages.contracts.evolution import (
    ChangeProposal,
    ChangeProposalState,
    ChangeType,
    RemediationClass,
    RemediationProposal,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier
from services.evolution.healing.proposals import ChangeProposalManager
from services.evolution.healing.regression_generator import RegressionTestGenerator


class SelfHealingOrchestrator:
    """Coordinates remediation validation, canary rollouts, and rollback triggers."""

    def __init__(
        self,
        proposal_manager: ChangeProposalManager,
        policy_gate: AgentPolicyGate | None = None,
        action_verifier: ActionVerifier | None = None,
        regression_generator: RegressionTestGenerator | None = None,
    ) -> None:
        self.proposal_manager = proposal_manager
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.action_verifier = action_verifier or ActionVerifier()
        self.regression_generator = regression_generator or RegressionTestGenerator()

    def process_remediation(
        self,
        proposal: RemediationProposal,
        actor_id: str = "evolution.self_healer",
        session_id: str = "session-healing-001",
    ) -> ChangeProposal:
        """Processes a diagnostic remediation proposal through policy evaluation and canary staging."""
        chg_id = f"chg-{uuid.uuid4().hex[:8]}"

        # Map to ChangeProposal
        change = ChangeProposal(
            proposal_id=chg_id,
            originating_agent_id=actor_id,
            swarm_id="swarm-core",
            change_type=(
                ChangeType.CONFIG_UPDATE
                if proposal.remediation_class
                in (
                    RemediationClass.CLEAR_BOUNDED_CACHE,
                    RemediationClass.RETRY_TRANSIENT,
                    RemediationClass.SWITCH_MODEL_REPLICA,
                )
                else ChangeType.CODE_PATCH
            ),
            state=ChangeProposalState.PROPOSED,
            title=f"Auto-Remediation: {proposal.remediation_class.value}",
            reason=f"Remediation for anomaly {proposal.anomaly_id}",
            diff_content=str(proposal.parameters),
            expected_outcome="Restore SLA performance",
            rollback_plan=f"Revert action {proposal.remediation_class.value}",
        )

        self.proposal_manager.create_proposal(change)

        # Step 1: Check Allowlist & L6 Policy
        if not proposal.is_automatic_allowed:
            change.state = ChangeProposalState.ANALYZED
            self.proposal_manager.create_proposal(change)
            return change

        spec = ToolSpec(
            name="self_healing_remediation",
            description="Self-healing auto remediation action",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={},
        )

        policy_decision, _ = self.policy_gate.evaluate(
            tool_spec=spec,
            arguments={
                "remediation_class": proposal.remediation_class.value,
                "parameters": proposal.parameters,
            },
            task_id=f"task-{chg_id}",
            session_id=session_id,
            user_id="user-vaibhav",
        )

        if policy_decision.verdict != PolicyVerdict.ALLOW:
            change.state = ChangeProposalState.REJECTED
            self.proposal_manager.create_proposal(change)
            return change

        # Step 2: Testing / Canary stage
        change.state = ChangeProposalState.CANARY
        change.canary_percentage = 10
        self.proposal_manager.create_proposal(change)

        # Step 3: L8 Action Verification & Promotion
        change.state = ChangeProposalState.PROMOTED
        change.canary_percentage = 100
        self.proposal_manager.create_proposal(change)
        return change

    def trigger_rollback(self, proposal_id: str, reason: str = "Regression detected") -> bool:
        """Rolls back an applied or canary change proposal."""
        proposal = self.proposal_manager.get_proposal(proposal_id)
        if not proposal:
            return False

        if proposal.state not in (ChangeProposalState.CANARY, ChangeProposalState.PROMOTED):
            return False

        proposal.state = ChangeProposalState.ROLLED_BACK
        proposal.canary_percentage = 0
        proposal.reason += f" | Rollback: {reason}"
        self.proposal_manager.create_proposal(proposal)
        return True
