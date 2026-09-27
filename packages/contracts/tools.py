"""Tool & Capability Schemas and Risk Classification.

Defines contracts for L5 Tool Runtime and L6 Policy Layer.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskClass(StrEnum):
    """Four-tier risk classification for all PIXEL tools."""
    READ = "READ"                                     # Zero side-effects; auto-approved
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"             # Local, easily undone state modifications
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION" # Public/external messaging or calls
    HIGH_IMPACT = "HIGH_IMPACT"                       # Destructive actions requiring explicit confirmation


class AuditLevel(StrEnum):
    """Level of audit trail required for tool execution."""
    NONE = "NONE"
    BASIC = "BASIC"
    DETAILED = "DETAILED"
    CRYPTOGRAPHIC = "CRYPTOGRAPHIC"


class ToolSpec(BaseModel):
    """Schema specification for a registered PIXEL capability/tool."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Clear explanation of tool capability")
    version: str = Field(default="1.0.0", description="SemVer string for tool specification")
    risk_class: RiskClass = Field(..., description="Safety and risk tier")
    parameters_schema: dict[str, Any] = Field(..., description="JSON Schema for input arguments")
    returns_schema: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for output payload")
    timeout_ms: int = Field(default=5000, ge=100, le=60000, description="Execution timeout in ms")
    requires_approval: bool = Field(default=False, description="Whether user confirmation is strictly mandatory")
    audit_level: AuditLevel = Field(default=AuditLevel.BASIC, description="Audit logging policy")


class ToolExecutionRequest(BaseModel):
    """Request payload to execute a specific capability."""
    tool_name: str = Field(..., description="Name of the target tool")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Typed arguments matching schema")
    session_id: str = Field(..., description="Active session identifier")
    trace_id: str = Field(..., description="Distributed OpenTelemetry trace ID")
    caller_agent_id: str | None = Field(default=None, description="Identifier of calling agent/subsystem")


class ToolExecutionResult(BaseModel):
    """Standardized output from a capability execution."""
    success: bool = Field(..., description="Whether the tool execution succeeded")
    output: Any = Field(default=None, description="Result payload if successful")
    error: str | None = Field(default=None, description="Detailed error message if failed")
    duration_ms: int = Field(default=0, ge=0, description="Elapsed execution duration in milliseconds")
    evidence: dict[str, Any] | None = Field(default=None, description="Verification evidence (e.g. exit code, diff)")
