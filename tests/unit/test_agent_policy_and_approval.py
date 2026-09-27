"""Unit tests for L6 Agent Policy Gate, Approval Flow, and Replay Defense."""

import pytest

from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import AuditLevel, RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate


@pytest.fixture
def policy_gate() -> AgentPolicyGate:
    return AgentPolicyGate(hmac_secret="test_secret_key_42")


def test_read_tool_auto_approved(policy_gate: AgentPolicyGate) -> None:
    spec = ToolSpec(
        name="read_file",
        description="Reads file",
        risk_class=RiskClass.READ,
        parameters_schema={"type": "object", "properties": {"path": {"type": "string"}}},
        audit_level=AuditLevel.BASIC,
    )

    decision, card = policy_gate.evaluate(
        tool_spec=spec,
        arguments={"path": "safe.txt"},
        task_id="t1",
        session_id="s1",
        user_id="u1",
    )

    assert decision.verdict == PolicyVerdict.ALLOW
    assert card is None


def test_sensitive_tool_requires_approval(policy_gate: AgentPolicyGate) -> None:
    spec = ToolSpec(
        name="delete_database",
        description="Destructive deletion",
        risk_class=RiskClass.HIGH_IMPACT,
        parameters_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        audit_level=AuditLevel.CRYPTOGRAPHIC,
    )

    # First attempt: Unconfirmed -> Should require user confirmation
    decision, card = policy_gate.evaluate(
        tool_spec=spec,
        arguments={"target": "prod_users"},
        task_id="t2",
        session_id="s2",
        user_id="u2",
    )

    assert decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION
    assert card is not None
    assert card.confirmation_token is not None
    assert card.tool_name == "delete_database"


def test_approval_token_validation_and_replay_defense(policy_gate: AgentPolicyGate) -> None:
    spec = ToolSpec(
        name="send_external_email",
        description="Sends external email",
        risk_class=RiskClass.EXTERNAL_COMMUNICATION,
        parameters_schema={"type": "object", "properties": {"recipient": {"type": "string"}}},
        audit_level=AuditLevel.DETAILED,
    )

    # 1. Generate approval card for recipient A
    args_a = {"recipient": "boss@example.com", "subject": "Quarterly Report"}
    _, card = policy_gate.evaluate(
        tool_spec=spec,
        arguments=args_a,
        task_id="t3",
        session_id="s3",
        user_id="u3",
    )
    assert card is not None
    valid_token = card.confirmation_token

    # 2. Confirm with exact matching arguments -> Should be ALLOWED
    decision_allowed, _ = policy_gate.evaluate(
        tool_spec=spec,
        arguments=args_a,
        task_id="t3",
        session_id="s3",
        user_id="u3",
        confirmation_token=valid_token,
        is_user_confirmed=True,
    )
    assert decision_allowed.verdict == PolicyVerdict.ALLOW

    # 3. Adversarial Attempt: Argument Tampering / Token Replay
    # Attacker tries to use the token approved for boss@example.com to send to attacker@evil.com
    tampered_args = {"recipient": "attacker@evil.com", "subject": "Stolen Data"}
    decision_denied, _ = policy_gate.evaluate(
        tool_spec=spec,
        arguments=tampered_args,
        task_id="t3",
        session_id="s3",
        user_id="u3",
        confirmation_token=valid_token,
        is_user_confirmed=True,
    )
    assert decision_denied.verdict == PolicyVerdict.DENY
    assert "Replay/Tamper Defense" in decision_denied.reason
