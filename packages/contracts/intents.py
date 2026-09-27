"""Intent Routing and Classification Contracts.

Defines normalized data structures for L3 Intent & Agent Routing.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntentRoutingType(StrEnum):
    """The execution pathway determined by the L3 Router."""

    DETERMINISTIC_FAST_PATH = "DETERMINISTIC_FAST_PATH"  # Bypasses LLM (<300ms)
    CONVERSATIONAL_QA = "CONVERSATIONAL_QA"  # Fast conversational model
    LANGGRAPH_AGENT = "LANGGRAPH_AGENT"  # Multi-step stateful reasoning graph
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"  # User ambiguity; requires clarification


class IntentPacket(BaseModel):
    """Normalized intent payload passed from the L3 Router to the execution pipeline."""

    raw_query: str = Field(..., description="Original user utterance")
    language: str = Field(
        default="en", description="Identified language code (e.g. en, hi, hinglish)"
    )
    routing_type: IntentRoutingType = Field(..., description="Selected routing path")
    target_intent: str | None = Field(
        default=None, description="Deterministic intent identifier if applicable"
    )
    extracted_entities: dict[str, Any] = Field(
        default_factory=dict, description="Parsed temporal/spatial entities"
    )
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Routing confidence score")
    session_id: str | None = Field(default=None, description="Associated session identifier")
    trace_id: str | None = Field(default=None, description="OpenTelemetry trace identifier")
