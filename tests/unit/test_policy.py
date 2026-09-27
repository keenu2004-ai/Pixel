"""Unit tests for L6 Policy Engine, Risk Classification, and Audit Records."""

from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import AuditLevel, RiskClass, ToolSpec
from packages.core.policy import PolicyEngine


def test_read_tool_auto_approved() -> None:
    spec = ToolSpec(
        name="read_calendar",
        description="Reads calendar events",
        risk_class=RiskClass.READ,
        parameters_schema={}
    )
    decision = PolicyEngine.evaluate_tool_request(spec, {})
    assert decision.verdict == PolicyVerdict.ALLOW
    assert decision.risk_class == RiskClass.READ


def test_high_impact_requires_confirmation() -> None:
    spec = ToolSpec(
        name="delete_project_database",
        description="Deletes database tables",
        risk_class=RiskClass.HIGH_IMPACT,
        parameters_schema={}
    )
    # Without user confirmation -> Requires confirmation
    decision = PolicyEngine.evaluate_tool_request(spec, {}, is_user_confirmed=False)
    assert decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION

    # With user confirmation -> Allowed
    approved = PolicyEngine.evaluate_tool_request(spec, {}, is_user_confirmed=True)
    assert approved.verdict == PolicyVerdict.ALLOW


def test_external_communication_requires_confirmation() -> None:
    spec = ToolSpec(
        name="send_sms",
        description="Sends external SMS message",
        risk_class=RiskClass.EXTERNAL_COMMUNICATION,
        parameters_schema={"type": "object", "required": ["recipient", "message"]}
    )
    decision = PolicyEngine.evaluate_tool_request(spec, {"recipient": "+919999999999", "message": "Hi"}, is_user_confirmed=False)
    assert decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION


def test_shell_injection_denied() -> None:
    spec = ToolSpec(
        name="execute_shell",
        description="Runs shell command",
        risk_class=RiskClass.HIGH_IMPACT,
        parameters_schema={"type": "object"}
    )
    decision = PolicyEngine.evaluate_tool_request(
        spec,
        {"command": "rm -rf / --no-preserve-root"},
        is_user_confirmed=True
    )
    assert decision.verdict == PolicyVerdict.DENY
    assert "Forbidden dangerous command" in decision.reason


def test_path_traversal_denied() -> None:
    spec = ToolSpec(
        name="write_file",
        description="Writes a file",
        risk_class=RiskClass.REVERSIBLE_WRITE,
        parameters_schema={"type": "object"}
    )
    decision = PolicyEngine.evaluate_tool_request(
        spec,
        {"path": "../../etc/shadow", "content": "hack"},
        is_user_confirmed=False
    )
    assert decision.verdict == PolicyVerdict.DENY
    assert "Path traversal" in decision.reason


def test_audit_record_generation() -> None:
    spec = ToolSpec(
        name="set_alarm",
        description="Sets clock alarm",
        risk_class=RiskClass.REVERSIBLE_WRITE,
        parameters_schema={},
        audit_level=AuditLevel.CRYPTOGRAPHIC
    )
    decision = PolicyEngine.evaluate_tool_request(spec, {"time": "07:00"})
    audit = PolicyEngine.create_audit_record(
        actor_id="user_123",
        tool_spec=spec,
        arguments={"time": "07:00"},
        decision=decision,
        trace_id="tr_789",
        execution_success=True
    )
    assert audit.actor_id == "user_123"
    assert audit.tool_name == "set_alarm"
    assert len(audit.arguments_hash) == 64  # SHA-256 length
    assert audit.verdict == PolicyVerdict.ALLOW
    assert audit.audit_level == AuditLevel.CRYPTOGRAPHIC
    assert audit.execution_success is True
