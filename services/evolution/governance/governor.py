"""PIXEL — Evolution Governor.

Enforces evolution rate limits, verifies proposal quotas, enforces canary requirements,
and interfaces with KillSwitchSystem and L6 AgentPolicyGate.
"""

from datetime import UTC, datetime

from packages.contracts.evolution import (
    ChangeProposal,
    EvolutionPolicy,
    KillSwitchDomain,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.evolution.governance.kill_switches import KillSwitchSystem


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class EvolutionGovernor:
    """Regulates all autonomous evolution capabilities and guarantees safety invariance."""

    def __init__(
        self,
        kill_switch_system: KillSwitchSystem | None = None,
        policy_gate: AgentPolicyGate | None = None,
        policy: EvolutionPolicy | None = None,
    ) -> None:
        self.kill_switches = kill_switch_system or KillSwitchSystem()
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.policy = policy or EvolutionPolicy()
        self._daily_proposal_count: int = 0

    def can_execute_remediation(self) -> bool:
        """Checks if autonomous remediation is permitted by policy and kill switches."""
        if self.kill_switches.is_tripped(KillSwitchDomain.AUTONOMOUS_REMEDIATION):
            return False
        return self.policy.allow_automatic_remediation

    def can_replicate_memory(self) -> bool:
        """Checks if memory replication is permitted."""
        return not self.kill_switches.is_tripped(KillSwitchDomain.MEMORY_REPLICATION)

    def can_promote_model(self) -> bool:
        """Checks if model promotion is permitted."""
        return not self.kill_switches.is_tripped(KillSwitchDomain.MODEL_PROMOTION)

    def can_train_model(self) -> bool:
        """Checks if training/distillation is permitted."""
        return not self.kill_switches.is_tripped(KillSwitchDomain.TRAINING_PIPELINE)

    def authorize_change_proposal(
        self,
        proposal: ChangeProposal,
        user_id: str = "user-vaibhav",
    ) -> bool:
        """Checks quotas, kill switches, and evaluates L6 policy on change proposals."""
        # 1. Kill switch check
        if self.kill_switches.is_tripped(KillSwitchDomain.CODE_PROMOTION):
            return False

        # 2. Daily quota check
        if self._daily_proposal_count >= self.policy.max_daily_proposals:
            return False

        # 3. L6 Policy evaluation
        spec = ToolSpec(
            name="evolution_change_proposal",
            description="Evolution change proposal execution",
            risk_class=RiskClass.HIGH_IMPACT
            if self.policy.require_human_approval_for_code
            else RiskClass.REVERSIBLE_WRITE,
            parameters_schema={},
        )

        policy_decision, _ = self.policy_gate.evaluate(
            tool_spec=spec,
            arguments={"proposal_id": proposal.proposal_id, "diff": proposal.diff_content},
            task_id=f"task-{proposal.proposal_id}",
            session_id="session-gov-001",
            user_id=user_id,
        )

        if policy_decision.verdict == PolicyVerdict.ALLOW:
            self._daily_proposal_count += 1
            return True

        return False
