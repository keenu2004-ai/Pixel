"""PIXEL — Phase 15 Intelligence, Personalization & Adaptive Personal Assistant Contracts.

Defines schemas and enums for:
1. User Model, Identity, and Privacy Preferences.
2. Structured Preferences (Language, Detail, Tone, Tool, Notification, Routine).
3. Memory Provenance, Confidence Tiers, Freshness, and Expiration.
4. Habits, Observed Patterns, and User-Governed Routines.
5. Goal and Task Continuity Models.
6. Personal Vocabulary, Entities, and Disambiguation.
7. Context Assembly, Ranking Signals, and Token Budgets.
8. Adaptive Response Strategies (Hinglish/Hindi Code-Switching, Tone, Depth).
9. User Corrections, Feedback Loops, and Reversible Learning.
10. Proactive Assistance Triggers, Anti-Annoyance Budgets, and Cross-Device Sync.
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


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# 1. Provenance, Confidence & Freshness Enums
# ============================================================================


class ProvenanceType(StrEnum):
    """Origin source and verification authority of personal knowledge."""

    EXPLICIT_USER = "EXPLICIT_USER"  # Direct user command ("My editor is VS Code")
    USER_CONFIRMED = "USER_CONFIRMED"  # Inferred pattern explicitly confirmed by user
    INFERRED = "INFERRED"  # High-confidence statistical inference from behavior
    OBSERVED = "OBSERVED"  # One-time behavioral observation
    SYSTEM_DERIVED = "SYSTEM_DERIVED"  # Derived from system configuration or device specs


class ConfidenceTier(StrEnum):
    """Standardized memory confidence tiers."""

    LOW = "LOW"  # 0.0 - 0.49: Observation only, never overrides rules
    MEDIUM = "MEDIUM"  # 0.5 - 0.79: Plausible inference, requires confirmation for major actions
    HIGH = "HIGH"  # 0.8 - 0.94: Well-established pattern or multiple observations
    USER_CONFIRMED = "USER_CONFIRMED"  # 0.95 - 1.0: Explicit ground truth from user


class MemoryCategory(StrEnum):
    """Taxonomy of personal knowledge retained by PIXEL."""

    IDENTITY = "IDENTITY"
    PREFERENCE = "PREFERENCE"
    COMMUNICATION_STYLE = "COMMUNICATION_STYLE"
    LANGUAGE = "LANGUAGE"
    ROUTINE = "ROUTINE"
    GOAL = "GOAL"
    PROJECT = "PROJECT"
    ENTITY = "ENTITY"
    DEVICE = "DEVICE"
    WORKFLOW = "WORKFLOW"
    EXPLICIT_INSTRUCTION = "EXPLICIT_INSTRUCTION"
    PRIVACY_RULE = "PRIVACY_RULE"


# ============================================================================
# 2. Structured Preferences & Style Adaptation
# ============================================================================


class ResponseLengthPreference(StrEnum):
    """Desired conciseness of assistant verbal and text outputs."""

    CONCISE = "CONCISE"  # Direct, minimal words, voice-optimized
    BALANCED = "BALANCED"  # Natural informative summary
    DETAILED = "DETAILED"  # Thorough, step-by-step technical breakdown


class TechnicalDepth(StrEnum):
    """User technical expertise level for code and system queries."""

    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    EXPERT = "EXPERT"


class AssistantTone(StrEnum):
    """Interpersonal communication tone."""

    CASUAL = "CASUAL"
    FORMAL = "FORMAL"
    FRIENDLY = "FRIENDLY"
    TECHNICAL = "TECHNICAL"


class LanguageMode(StrEnum):
    """Primary conversational language and code-switching mode."""

    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"
    AUTO_DETECT = "auto"


class UserPreferenceProfile(BaseModel):
    """Comprehensive user preference settings with explicit vs inferred separation."""

    user_id: str = "default_user"
    language_mode: LanguageMode = LanguageMode.AUTO_DETECT
    preferred_spoken_language: str = "en"
    response_length: ResponseLengthPreference = ResponseLengthPreference.CONCISE
    technical_depth: TechnicalDepth = TechnicalDepth.EXPERT
    tone: AssistantTone = AssistantTone.FRIENDLY
    preferred_code_editor: str = "VS Code"
    preferred_terminal_shell: str = "powershell"
    preferred_browser: str = "chrome"
    auto_voice_response: bool = True
    proactive_assistance_enabled: bool = True
    max_proactive_notifications_per_day: int = Field(default=5, ge=0, le=24)
    ask_before_external_actions: bool = True
    ask_before_file_modifications: bool = True
    local_models_only: bool = False
    custom_preferences: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime = Field(default_factory=_utc_now)


# ============================================================================
# 3. Personal Memory Record (with Provenance, Freshness, & Confidence)
# ============================================================================


class PersonalMemoryRecord(BaseModel):
    """Durable semantic or episodic fact with full audit trail and lifecycle rules."""

    record_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    category: MemoryCategory = MemoryCategory.PREFERENCE
    key: str = Field(..., description="Dot-notated key e.g. preference.editor")
    value: Any = Field(..., description="Scalar or structured value")
    provenance: ProvenanceType = ProvenanceType.EXPLICIT_USER
    source_context: str = Field(default="user_dialogue", description="Origin utterance or session")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_tier: ConfidenceTier = ConfidenceTier.USER_CONFIRMED
    is_active: bool = True
    superseded_by: str | None = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    last_confirmed_at: datetime | None = None
    expires_at: datetime | None = None
    ttl_seconds: int | None = None  # None for permanent facts

    def is_stale(self) -> bool:
        """Determines if the memory record has expired based on TTL or explicit timestamp."""
        if not self.is_active:
            return True
        if self.expires_at is not None and datetime.now(UTC) > self.expires_at:
            return True
        if self.ttl_seconds is not None:
            age = (datetime.now(UTC) - self.updated_at).total_seconds()
            if age > self.ttl_seconds:
                return True
        return False


# ============================================================================
# 4. Habits, Observed Patterns & User-Governed Routines
# ============================================================================


class PatternStatus(StrEnum):
    """Lifecycle status of behavioral patterns."""

    OBSERVED = "OBSERVED"  # Detected multiple times, pending user confirmation
    USER_APPROVED = "USER_APPROVED"  # User authorized for automated suggestion / routine
    REJECTED = "REJECTED"  # User explicitly declined
    DISABLED = "DISABLED"  # Temporarily paused


class HabitPattern(BaseModel):
    """Repeated behavioral pattern detected across sessions."""

    habit_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    name: str
    description: str
    trigger_condition: str  # e.g. "time:09:00", "app_opened:vscode", "task_completed:build"
    associated_action: str  # e.g. "open_dashboard", "run_daily_tests"
    action_parameters: dict[str, Any] = Field(default_factory=dict)
    occurrence_count: int = Field(default=1, ge=1)
    first_observed_at: datetime = Field(default_factory=_utc_now)
    last_observed_at: datetime = Field(default_factory=_utc_now)
    status: PatternStatus = PatternStatus.OBSERVED
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class RoutineStep(BaseModel):
    """A deterministic or autonomous step within a user-governed routine."""

    step_id: int
    name: str
    tool_or_action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


class UserRoutine(BaseModel):
    """Explicitly configured multi-action routine (e.g. morning, coding, evening)."""

    routine_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    name: str  # e.g. "Morning Briefing", "Start Work Session"
    schedule_cron: str | None = None  # e.g. "0 9 * * 1-5"
    voice_trigger_phrases: list[str] = Field(default_factory=list)
    steps: list[RoutineStep] = Field(default_factory=list)
    is_active: bool = True
    last_run_at: datetime | None = None
    created_at: datetime = Field(default_factory=_utc_now)


# ============================================================================
# 5. Goal & Task Continuity Contracts
# ============================================================================


class GoalStatus(StrEnum):
    """Progression state of an overarching user goal."""

    PROPOSED = "PROPOSED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"


class PersonalGoal(BaseModel):
    """A long-term project or objective spanning multiple sessions and days."""

    goal_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    title: str  # e.g. "Migrate HRMS backend to PostgreSQL", "Implement Voice Barge-In"
    description: str = ""
    status: GoalStatus = GoalStatus.ACTIVE
    priority: int = Field(default=1, ge=1, le=5)  # 1 = Highest, 5 = Lowest
    tags: list[str] = Field(default_factory=list)
    active_project_path: str | None = None
    milestones: list[dict[str, Any]] = Field(default_factory=list)
    associated_tasks: list[str] = Field(default_factory=list)
    last_worked_on: datetime = Field(default_factory=_utc_now)
    created_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = None


# ============================================================================
# 6. Personal Vocabulary & Entity Resolution Contracts
# ============================================================================


class EntityType(StrEnum):
    """Categories of personal entities referenced by the user."""

    PERSON = "PERSON"
    PROJECT = "PROJECT"
    REPOSITORY = "REPOSITORY"
    DEVICE = "DEVICE"
    APPLICATION = "APPLICATION"
    FILE_OR_PATH = "FILE_OR_PATH"
    LOCATION = "LOCATION"
    SERVICE = "SERVICE"


class PersonalEntity(BaseModel):
    """A user-specific alias, nickname, contact, or entity mapping."""

    entity_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    entity_type: EntityType
    canonical_name: str  # e.g. "Rahul Sharma", "c:/Users/Vaibhav/Pixel"
    aliases: list[str] = Field(default_factory=list)  # e.g. ["rahul", "brother", "lead dev"]
    context_metadata: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=_utc_now)
    last_referenced_at: datetime = Field(default_factory=_utc_now)


class EntityResolutionResult(BaseModel):
    """Outcome of resolving an utterance token to a known personal entity."""

    matched: bool
    ambiguous: bool
    query_term: str
    resolved_entity: PersonalEntity | None = None
    candidate_entities: list[PersonalEntity] = Field(default_factory=list)
    clarification_prompt: str | None = None


# ============================================================================
# 7. Context Engine, Ranking & Assembly Contracts
# ============================================================================


class RankedContextItem(BaseModel):
    """An individual piece of context scored for relevance and injected into prompt."""

    source_type: str  # PREFERENCE, GOAL, FACT, EPISODE, ENTITY, ROUTINE, DEVICE
    key: str
    content: str
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    recency_score: float = Field(default=1.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    final_rank_score: float = Field(..., ge=0.0, le=1.0)
    provenance: ProvenanceType = ProvenanceType.EXPLICIT_USER


class AssembledPersonalContext(BaseModel):
    """The bounded, ranked minimal context payload assembled for the LLM/Planner."""

    user_id: str
    session_id: str
    query: str
    items: list[RankedContextItem] = Field(default_factory=list)
    injected_facts_summary: str = ""
    active_goal_title: str | None = None
    language_recommendation: str = "en"
    tone_recommendation: str = "concise"
    total_tokens_estimated: int = 0
    assembly_latency_ms: float = 0.0


# ============================================================================
# 8. User Correction & Reversible Learning Contracts
# ============================================================================


class CorrectionType(StrEnum):
    """Nature of user corrective feedback."""

    PREFERENCE_CHANGE = "PREFERENCE_CHANGE"  # "I use Chrome now, not Edge"
    FACT_CORRECTION = "FACT_CORRECTION"  # "No, Rahul is my manager"
    ENTITY_MAPPING = "ENTITY_MAPPING"  # "By 'Pixel' I mean the root repo"
    BEHAVIOR_FEEDBACK = "BEHAVIOR_FEEDBACK"  # "Don't be so wordy", "Too fast"
    REVERT_LAST = "REVERT_LAST"  # "Undo that change", "Forget what you learned"


class UserCorrectionEvent(BaseModel):
    """Detected user correction with hypothesis and update action."""

    correction_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    session_id: str
    user_utterance: str
    previous_assistant_response: str | None = None
    correction_type: CorrectionType
    target_key: str
    old_value: Any | None = None
    new_value: Any
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    requires_explicit_confirmation: bool = False
    applied: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


# ============================================================================
# 9. Proactive Assistance & Anti-Annoyance Contracts
# ============================================================================


class ProactiveTriggerType(StrEnum):
    """Categories of conditions that may trigger proactive suggestions."""

    UPCOMING_COMMITMENT = "UPCOMING_COMMITMENT"
    UNFINISHED_TASK = "UNFINISHED_TASK"
    KNOWN_DEADLINE = "KNOWN_DEADLINE"
    REPEATED_WORKFLOW = "REPEATED_WORKFLOW"
    SYSTEM_DIAGNOSTIC = "SYSTEM_DIAGNOSTIC"
    ROUTINE_PROMPT = "ROUTINE_PROMPT"


class ProactiveActionSuggestion(BaseModel):
    """Bounded proactive suggestion presented safely to the user."""

    suggestion_id: str = Field(default_factory=_gen_id)
    user_id: str = Field(default="default_user")
    trigger_type: ProactiveTriggerType
    headline: str
    suggested_action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    reasoning: str
    risk_level: str = "LOW"
    dismissed: bool = False
    accepted: bool = False
    created_at: datetime = Field(default_factory=_utc_now)


class ProactiveBudgetState(BaseModel):
    """Rate-limiting state tracking proactive interruptions to prevent user annoyance."""

    user_id: str = "default_user"
    hourly_suggestions_count: int = 0
    daily_suggestions_count: int = 0
    last_suggestion_timestamp: datetime | None = None
    cooldown_seconds: int = 300  # Minimum 5 minutes between proactive prompts
    accepted_count: int = 0
    dismissed_count: int = 0
    ignored_count: int = 0


# ============================================================================
# 10. Cross-Device Personal Context Sync Contracts
# ============================================================================


class PersonalContextSyncDelta(BaseModel):
    """Cryptographically verifiable delta of personal memory and preferences for mesh sync."""

    delta_id: str = Field(default_factory=_gen_id)
    user_id: str
    origin_device_id: str
    target_device_id: str | None = None  # None = Broadcast to mesh
    updated_facts: list[PersonalMemoryRecord] = Field(default_factory=list)
    purged_keys: list[str] = Field(default_factory=list)
    updated_preferences: dict[str, Any] = Field(default_factory=dict)
    active_goals: list[PersonalGoal] = Field(default_factory=list)
    entities: list[PersonalEntity] = Field(default_factory=list)
    created_at: str = Field(default_factory=_utc_now_iso)
    signature: str = ""
