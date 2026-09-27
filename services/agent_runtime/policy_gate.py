"""L6 Agent Policy Gate & Approval Security Enforcer.

Enforces non-bypassable policy decisions on all agent-requested actions,
signs ApprovalCards with cryptographic HMACs, defends against approval replay/tampering,
and generates immutable audit records.
"""

import hashlib
import hmac
import json
import logging
from typing import Any

from packages.contracts.agent import ApprovalCard
from packages.contracts.security import AuditRecord, PolicyDecision, PolicyVerdict
from packages.contracts.tools import ToolSpec
from packages.core.policy import PolicyEngine

logger = logging.getLogger(__name__)


class AgentPolicyGate:
    """Non-bypassable policy evaluation gate for agent capabilities."""

    def __init__(self, hmac_secret: str = "pixel_agent_secret_key_v1") -> None:
        self.hmac_secret = hmac_secret.encode("utf-8")
        self.audit_log: list[AuditRecord] = []

    def compute_arguments_hash(self, arguments: dict[str, Any]) -> str:
        """Computes deterministic SHA-256 hash of structured arguments."""
        try:
            serialized = json.dumps(arguments, sort_keys=True, default=str)
        except Exception:
            serialized = str(arguments)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def generate_confirmation_token(
        self,
        task_id: str,
        session_id: str,
        user_id: str,
        tool_name: str,
        arguments_hash: str,
    ) -> str:
        """Generates an HMAC-SHA256 confirmation token bound to action identity and arguments."""
        payload = f"{task_id}:{session_id}:{user_id}:{tool_name}:{arguments_hash}"
        return hmac.new(self.hmac_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_confirmation_token(
        self,
        token: str,
        task_id: str,
        session_id: str,
        user_id: str,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> tuple[bool, str | None]:
        """Validates that confirmation token was signed for the EXACT tool, user, and arguments."""
        args_hash = self.compute_arguments_hash(arguments)
        expected_token = self.generate_confirmation_token(
            task_id=task_id,
            session_id=session_id,
            user_id=user_id,
            tool_name=tool_name,
            arguments_hash=args_hash,
        )

        if not hmac.compare_digest(token, expected_token):
            return False, "Approval token is invalid, expired, or does not match the requested action/arguments (Replay/Tamper Defense)."
        return True, None

    def evaluate(
        self,
        tool_spec: ToolSpec,
        arguments: dict[str, Any],
        task_id: str,
        session_id: str,
        user_id: str,
        confirmation_token: str | None = None,
        is_user_confirmed: bool = False,
    ) -> tuple[PolicyDecision, ApprovalCard | None]:
        """Evaluates tool invocation against L6 Policy Engine and constructs ApprovalCard if needed."""
        # Check if user confirmed with valid token
        valid_user_confirmation = False
        if is_user_confirmed and confirmation_token:
            is_valid, err = self.verify_confirmation_token(
                token=confirmation_token,
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                tool_name=tool_spec.name,
                arguments=arguments,
            )
            if is_valid:
                valid_user_confirmation = True
            else:
                logger.warning("Invalid confirmation token presented for tool '%s': %s", tool_spec.name, err)
                return PolicyDecision(
                    verdict=PolicyVerdict.DENY,
                    risk_class=tool_spec.risk_class,
                    reason=f"Security Alert: {err}",
                ), None

        decision = PolicyEngine.evaluate_tool_request(
            tool_spec=tool_spec,
            arguments=arguments,
            is_user_confirmed=valid_user_confirmation,
        )

        approval_card: ApprovalCard | None = None
        if decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION:
            args_hash = self.compute_arguments_hash(arguments)
            token = self.generate_confirmation_token(
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                tool_name=tool_spec.name,
                arguments_hash=args_hash,
            )
            decision.confirmation_token = token
            approval_card = ApprovalCard(
                task_id=task_id,
                session_id=session_id,
                user_id=user_id,
                tool_name=tool_spec.name,
                arguments=arguments,
                arguments_hash=args_hash,
                risk_class=decision.risk_class.value,
                reason=decision.reason,
                confirmation_token=token,
            )

        return decision, approval_card

    def record_audit(
        self,
        actor_id: str,
        tool_spec: ToolSpec,
        arguments: dict[str, Any],
        decision: PolicyDecision,
        trace_id: str,
        execution_success: bool | None = None,
    ) -> AuditRecord:
        """Records audit event into in-memory/persistent audit ledger."""
        record = PolicyEngine.create_audit_record(
            actor_id=actor_id,
            tool_spec=tool_spec,
            arguments=arguments,
            decision=decision,
            trace_id=trace_id,
            execution_success=execution_success,
        )
        self.audit_log.append(record)
        return record
