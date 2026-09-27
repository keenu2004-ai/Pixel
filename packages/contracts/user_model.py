"""PIXEL — Formal User Model Contract.

Defines the top-level aggregate UserModel representing the user's preferences,
identity traits, communication styles, goals, routines, entities, and privacy boundaries.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from packages.contracts.personalization import (
    HabitPattern,
    PersonalEntity,
    PersonalGoal,
    PersonalMemoryRecord,
    UserPreferenceProfile,
    UserRoutine,
)


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class UserIdentityProfile(BaseModel):
    """Core user identity information."""

    user_id: str = "default_user"
    display_name: str = "User"
    preferred_nickname: str | None = None
    timezone: str = "UTC"
    locale: str = "en_IN"
    created_at: datetime = Field(default_factory=_utc_now)


class UserPrivacyPolicy(BaseModel):
    """User-governed privacy and retention policy."""

    allow_inferred_preferences: bool = True
    allow_habit_detection: bool = True
    allow_proactive_assistance: bool = True
    allow_cloud_model_routing: bool = True
    retain_interaction_transcripts: bool = True
    transcript_retention_days: int = 30
    auto_scrub_pii: bool = True
    restricted_keywords: list[str] = Field(default_factory=list)


class UserModel(BaseModel):
    """Unified aggregate representation of a PIXEL user."""

    user_id: str = "default_user"
    identity: UserIdentityProfile = Field(default_factory=UserIdentityProfile)
    preferences: UserPreferenceProfile = Field(default_factory=UserPreferenceProfile)
    privacy_policy: UserPrivacyPolicy = Field(default_factory=UserPrivacyPolicy)
    active_goals: list[PersonalGoal] = Field(default_factory=list)
    routines: list[UserRoutine] = Field(default_factory=list)
    habits: list[HabitPattern] = Field(default_factory=list)
    entities: list[PersonalEntity] = Field(default_factory=list)
    active_facts: list[PersonalMemoryRecord] = Field(default_factory=list)
    custom_metadata: dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    updated_at: datetime = Field(default_factory=_utc_now)
