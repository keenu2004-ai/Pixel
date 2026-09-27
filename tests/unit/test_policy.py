"""Unit tests for L6 Policy Engine and risk classification."""

from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from packages.core.policy import PolicyEngine


def test_read_tool_auto_approved() -> None:
    spec = ToolSpec(
        name="read_calendar",
        description="Reads events",
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
    # Without user confirmation
    decision = PolicyEngine.evaluate_tool_request(spec, {}, is_user_confirmed=False)
    assert decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION

    # With user confirmation
    approved = PolicyEngine.evaluate_tool_request(spec, {}, is_user_confirmed=True)
    assert approved.verdict == PolicyVerdict.ALLOW


def test_shell_injection_denied() -> None:
    spec = ToolSpec(
        name="execute_shell",
        description="Runs shell",
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
