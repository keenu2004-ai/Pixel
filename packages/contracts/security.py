"""Security and Policy Evaluation Contracts."""

from enum import StrEnum

from pydantic import BaseModel, Field

from packages.contracts.tools import RiskClass


class PolicyVerdict(StrEnum):
    """Evaluation verdict for an attempted action."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_USER_CONFIRMATION = "REQUIRE_USER_CONFIRMATION"


class PolicyDecision(BaseModel):
    """Output of L6 Policy Engine evaluating a tool execution request."""
    verdict: PolicyVerdict = Field(..., description="Action verdict")
    risk_class: RiskClass = Field(..., description="Assigned risk class")
    reason: str = Field(..., description="Audit rationale for decision")
    confirmation_token: str | None = Field(default=None, description="Signed token if approval is needed")
