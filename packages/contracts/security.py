"""Security, Policy, and Audit Trail Contracts.

Defines data models for L6 Policy Evaluation and L10 Security Auditing.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.contracts.tools import AuditLevel, RiskClass


def _generate_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class PolicyVerdict(StrEnum):
    """Evaluation verdict for an attempted tool execution."""
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_USER_CONFIRMATION = "REQUIRE_USER_CONFIRMATION"


class PolicyDecision(BaseModel):
    """Output of L6 Policy Engine evaluating an action request."""
    verdict: PolicyVerdict = Field(..., description="Action verdict")
    risk_class: RiskClass = Field(..., description="Assigned risk class")
    reason: str = Field(..., description="Audit rationale explaining verdict")
    confirmation_token: str | None = Field(default=None, description="Signed token if approval is needed")


class AuthToken(BaseModel):
    """Identity and authorization token."""
    user_id: str = Field(..., description="User identity")
    device_id: str = Field(..., description="Device identity")
    scopes: list[str] = Field(default_factory=list, description="Granted capability scopes")
    expires_at: datetime = Field(..., description="Token expiration UTC timestamp")


class AuditRecord(BaseModel):
    """Immutable audit trail entry for tool executions and security decisions."""
    audit_id: str = Field(default_factory=_generate_id, description="Unique audit record ID")
    timestamp: datetime = Field(default_factory=_utc_now, description="Event timestamp in UTC")
    actor_id: str = Field(..., description="Actor ID (User or Agent ID)")
    tool_name: str = Field(..., description="Name of executed tool")
    arguments_hash: str = Field(..., description="SHA-256 hash or sanitized summary of input arguments")
    risk_class: RiskClass = Field(..., description="Risk class at evaluation time")
    verdict: PolicyVerdict = Field(..., description="Policy decision verdict")
    audit_level: AuditLevel = Field(default=AuditLevel.BASIC, description="Applied audit level")
    execution_success: bool | None = Field(default=None, description="Outcome of execution if permitted")
    trace_id: str = Field(..., description="Distributed OpenTelemetry trace ID")
