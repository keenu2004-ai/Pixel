"""Tool & Capability Schemas and Risk Classification."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskClass(StrEnum):
    """Four-tier risk classification for all PIXEL tools."""
    READ = "READ"                                     # Zero side-effects; auto-approved
    REVERSIBLE_WRITE = "REVERSIBLE_WRITE"             # Local, easily undone state modifications
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION" # Public/external messaging or calls
    HIGH_IMPACT = "HIGH_IMPACT"                       # Destructive actions requiring explicit confirmation


class ToolSpec(BaseModel):
    """Schema specification for a registered PIXEL tool."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Clear explanation of tool capability")
    risk_class: RiskClass = Field(..., description="Safety and risk tier")
    parameters_schema: dict[str, Any] = Field(..., description="JSON Schema for input arguments")
    timeout_ms: int = Field(default=5000, ge=100, le=60000, description="Execution timeout in ms")
    requires_approval: bool = Field(default=False, description="Whether user confirmation is strictly mandatory")


class ToolExecutionRequest(BaseModel):
    """Request payload to execute a specific tool."""
    tool_name: str = Field(..., description="Name of the target tool")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Typed arguments matching schema")
    session_id: str = Field(..., description="Active session identifier")
    trace_id: str = Field(..., description="Distributed OpenTelemetry trace ID")


class ToolExecutionResult(BaseModel):
    """Standardized output from a tool execution."""
    success: bool = Field(..., description="Whether the tool succeeded")
    output: Any = Field(default=None, description="Result payload if successful")
    error: str | None = Field(default=None, description="Detailed error message if failed")
    duration_ms: int = Field(default=0, description="Elapsed execution duration")
    evidence: dict[str, Any] | None = Field(default=None, description="Verification evidence")
