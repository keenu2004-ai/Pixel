"""Agent Runtime Contracts, State Schemas, and Planning Primitives.

Defines schemas for L4 LangGraph Agent Runtime, execution states,
checkpoints, action approval cards, and L8 verification results.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.contracts.intents import IntentPacket
from packages.contracts.rag import RAGContext
from packages.contracts.security import PolicyDecision
from packages.contracts.tools import ToolExecutionResult


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AgentExecutionStatus(StrEnum):
    """Lifecycle execution status of an agent task."""
    INITIALIZED = "INITIALIZED"
    PLANNING = "PLANNING"
    EXECUTING = "EXECUTING"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    VERIFYING = "VERIFYING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    POLICY_DENIED = "POLICY_DENIED"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"
    CANCELLED = "CANCELLED"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"


class StepStatus(StrEnum):
    """Status of an individual plan step."""
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class PlanStep(BaseModel):
    """Structured step within a task execution plan."""
    step_id: int = Field(..., ge=1, description="Sequential step index")
    description: str = Field(..., description="Action description")
    tool_name: str | None = Field(default=None, description="Target tool if step executes a tool")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    dependencies: list[int] = Field(default_factory=list, description="Step indices that must succeed before this step")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Execution status of this step")
    result: Any = Field(default=None, description="Result output upon step completion")
    error: str | None = Field(default=None, description="Error message if step failed")


class TaskPlan(BaseModel):
    """Structured execution plan formulated by the Agent Planner."""
    plan_id: str = Field(default_factory=_gen_id, description="Unique plan identifier")
    goal: str = Field(..., description="High-level user goal")
    steps: list[PlanStep] = Field(default_factory=list, description="Ordered plan steps")
    current_step_index: int = Field(default=0, ge=0, description="Pointer to current executing step")
    is_complete: bool = Field(default=False, description="Whether all steps have executed")


class ApprovalCard(BaseModel):
    """Interactive approval card payload requiring explicit user authorization."""
    approval_id: str = Field(default_factory=_gen_id, description="Unique approval request ID")
    task_id: str = Field(..., description="Associated agent task ID")
    session_id: str = Field(..., description="Session identifier")
    user_id: str = Field(..., description="User identity")
    tool_name: str = Field(..., description="Sensitive tool to be executed")
    arguments: dict[str, Any] = Field(..., description="Exact arguments to be executed")
    arguments_hash: str = Field(..., description="Deterministic SHA-256 hash of arguments (replay defense)")
    risk_class: str = Field(..., description="Risk class at evaluation time")
    reason: str = Field(..., description="Rationale for requiring approval")
    confirmation_token: str = Field(..., description="HMAC-signed confirmation token")
    created_at: datetime = Field(default_factory=_utc_now)
    is_resolved: bool = Field(default=False, description="Whether user has acted on this card")
    user_approved: bool | None = Field(default=None, description="User decision: True=approve, False=reject")


class VerificationResult(BaseModel):
    """Outcome of L8 post-execution state verification."""
    is_verified: bool = Field(..., description="Whether post-execution state matches expected outcome")
    tool_name: str = Field(..., description="Executed tool name")
    verification_type: str = Field(default="deterministic", description="Type of verification (deterministic, state_check, heuristic)")
    details: str = Field(..., description="Verification summary or error details")
    evidence: dict[str, Any] = Field(default_factory=dict, description="Collected state evidence")


class AgentState(BaseModel):
    """Canonical typed state for PIXEL LangGraph Agent Runtime."""
    task_id: str = Field(default_factory=_gen_id, description="Unique task identifier")
    session_id: str = Field(default="default_session", description="Associated session ID")
    user_id: str = Field(default="default_user", description="User ID")
    trace_id: str = Field(default_factory=_gen_id, description="OpenTelemetry trace ID")

    # Input Intent & Context
    user_query: str = Field(..., description="Initial user prompt")
    intent_packet: IntentPacket | None = Field(default=None, description="Parsed L3 Intent Packet")
    working_memory: list[dict[str, str]] = Field(default_factory=list, description="Recent conversation turns")
    semantic_facts: list[dict[str, Any]] = Field(default_factory=list, description="Relevant user facts")
    rag_context: RAGContext | None = Field(default=None, description="Retrieved external knowledge context")

    # Execution & Planning
    plan: TaskPlan | None = Field(default=None, description="Active execution plan")
    status: AgentExecutionStatus = Field(default=AgentExecutionStatus.INITIALIZED, description="Current execution status")
    current_step: int = Field(default=0, ge=0, description="Current step counter")
    max_steps: int = Field(default=10, ge=1, le=50, description="Hard bound on graph steps to prevent loops")

    # Tool Execution & Policy Gate
    pending_tool_name: str | None = Field(default=None, description="Next tool requested for execution")
    pending_tool_arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments for pending tool")
    last_policy_decision: PolicyDecision | None = Field(default=None, description="L6 Policy verdict")
    pending_approval: ApprovalCard | None = Field(default=None, description="Pending approval card if paused")
    tool_history: list[dict[str, Any]] = Field(default_factory=list, description="History of executed tools and results")
    last_tool_result: ToolExecutionResult | None = Field(default=None, description="Result of most recent tool execution")
    last_verification: VerificationResult | None = Field(default=None, description="Result of post-execution verification")

    # Final Output & Error Tracking
    final_response: str | None = Field(default=None, description="Final structured assistant response")
    error: str | None = Field(default=None, description="Error message if task failed")
    retry_count: int = Field(default=0, ge=0, description="Number of transient retries attempted")
    max_retries: int = Field(default=3, ge=0, le=5, description="Maximum retry threshold")
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class AgentCheckpoint(BaseModel):
    """Persisted checkpoint wrapper for state recovery across crashes/restarts."""
    checkpoint_id: str = Field(default_factory=_gen_id, description="Checkpoint record ID")
    task_id: str = Field(..., description="Task ID")
    session_id: str = Field(..., description="Session ID")
    version: int = Field(default=1, ge=1, description="State schema version")
    state_json: str = Field(..., description="Serialized AgentState JSON")
    status: AgentExecutionStatus = Field(..., description="Status at checkpoint time")
    created_at: datetime = Field(default_factory=_utc_now)
