"""Memory Tiering and Lifecycle Contracts for PIXEL.

Defines typed schemas for Working, Episodic, Semantic, Procedural, and Device Memory.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class MemoryTier(StrEnum):
    """The 5 architectural memory tiers in PIXEL."""

    WORKING = "WORKING"  # Session scratchpad, ephemeral
    EPISODIC = "EPISODIC"  # Specific interaction events, time-indexed
    SEMANTIC = "SEMANTIC"  # User profile, verified facts, preferences
    PROCEDURAL = "PROCEDURAL"  # Reusable automation workflows
    DEVICE = "DEVICE"  # Local network nodes & capabilities


class FactRecord(BaseModel):
    """A durable semantic fact or preference extracted from user interactions."""

    fact_id: str = Field(default_factory=_gen_id, description="Unique fact identifier")
    user_id: str = Field(..., description="Target user identifier")
    category: str = Field(
        default="general", description="Fact category (e.g. preferences, identity, work)"
    )
    key: str = Field(..., description="Canonical fact key (e.g. user.preferred_editor)")
    value: Any = Field(..., description="Structured or scalar fact value")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score")
    provenance: str = Field(
        default="user_explicit", description="Source utterance or reasoning chain"
    )
    superseded_by: str | None = Field(
        default=None, description="ID of newer fact that replaces this"
    )
    is_active: bool = Field(default=True, description="Whether this fact is currently active")
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


class EpisodeRecord(BaseModel):
    """Time-indexed episodic interaction summary with vector embeddings."""

    episode_id: str = Field(default_factory=_gen_id, description="Unique episode identifier")
    user_id: str = Field(..., description="Target user identifier")
    session_id: str = Field(..., description="Source session identifier")
    summary: str = Field(..., description="Sanitized concise interaction summary")
    interaction_type: str = Field(
        default="conversation", description="Type of episode (e.g. task, chat, coding)"
    )
    embedding: list[float] = Field(
        default_factory=list, description="Vector embedding representation"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Structured contextual metadata"
    )
    created_at: datetime = Field(default_factory=_utc_now)


class PIIScrubResult(BaseModel):
    """Output of PII & secret redaction pipeline."""

    cleaned_text: str = Field(
        ..., description="Text with sensitive tokens replaced by safe placeholders"
    )
    detected_entities: list[dict[str, Any]] = Field(
        default_factory=list, description="List of detected PII entities"
    )
    has_secrets: bool = Field(
        default=False, description="True if API keys, passwords, or credentials detected"
    )
    redaction_count: int = Field(default=0, ge=0, description="Total number of redacted items")
