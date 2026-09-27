"""PIXEL — Unified Personalization Manager Facade.

Integrates all Phase 15 intelligence and adaptation capabilities:
- Formal User Model & Structured Preferences
- Conflict Resolution & Explainability
- Habit Detection & User-Governed Routines
- Goal & Task Continuity Across Sessions
- Personal Vocabulary & Ambiguity-Free Entity Resolution
- Minimal Relevant Context Assembly & Poisoning Defense
- Adaptive Response Styling & Hinglish Code-Switching
- Reversible User Correction Learning Loop
- Cross-Device Mesh Synchronization & Right-to-Forget Cascades.
"""

import logging
from typing import Any

from packages.contracts.personalization import (
    AssembledPersonalContext,
    EntityResolutionResult,
    EntityType,
    HabitPattern,
    PersonalContextSyncDelta,
    PersonalEntity,
    PersonalGoal,
    PersonalMemoryRecord,
    ProactiveActionSuggestion,
    ProactiveTriggerType,
    UserCorrectionEvent,
    UserPreferenceProfile,
    UserRoutine,
)
from packages.contracts.user_model import UserModel
from services.personalization.adaptive_strategy import AdaptiveResponseStrategy
from services.personalization.context_engine import ContextEngine
from services.personalization.correction_learner import CorrectionLearner
from services.personalization.entity_resolver import EntityResolver
from services.personalization.goal_tracker import GoalTracker
from services.personalization.habit_routine_engine import HabitRoutineEngine
from services.personalization.poisoning_defense import MemoryPoisoningDefense
from services.personalization.preference_engine import PreferenceEngine
from services.personalization.sync_manager import CrossDeviceSyncManager
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class PersonalizationManager:
    """Master coordinator for PIXEL personalization and adaptive assistant runtime."""

    def __init__(
        self,
        db_path: str = "data/persistence/pixel_user_model.db",
        user_model_store: UserModelStore | None = None,
    ) -> None:
        self.store = user_model_store or UserModelStore(db_path=db_path)
        self.preference_engine = PreferenceEngine(user_model_store=self.store)
        self.goal_tracker = GoalTracker(user_model_store=self.store)
        self.entity_resolver = EntityResolver(user_model_store=self.store)
        self.habit_engine = HabitRoutineEngine(user_model_store=self.store)
        self.correction_learner = CorrectionLearner(preference_engine=self.preference_engine)
        self.sync_manager = CrossDeviceSyncManager(user_model_store=self.store)
        self.context_engine = ContextEngine(
            user_model_store=self.store,
            preference_engine=self.preference_engine,
            goal_tracker=self.goal_tracker,
            entity_resolver=self.entity_resolver,
        )

    def close(self) -> None:
        """Closes database connection."""
        self.store.close()

    async def get_user_model(self, user_id: str = "default_user") -> UserModel:
        """Retrieves user model aggregate."""
        return await self.store.get_user_model(user_id=user_id)

    async def get_preferences(self, user_id: str = "default_user") -> UserPreferenceProfile:
        """Retrieves structured user preference profile."""
        return await self.preference_engine.get_preference_profile(user_id=user_id)

    async def set_preference(
        self,
        key: str,
        value: Any,
        user_id: str = "default_user",
        source_context: str = "user_setting",
    ) -> PersonalMemoryRecord:
        """Sets an explicit user preference with full provenance and confidence 1.0."""
        # Validate against poisoning attacks
        is_safe, reason = MemoryPoisoningDefense.inspect_memory_candidate(
            key=key, value=value, provenance=source_context
        )
        if not is_safe:
            raise ValueError(f"Preference rejected by Security & Poisoning Defense: {reason}")

        return await self.preference_engine.set_explicit_preference(
            key=key, value=value, user_id=user_id, source_context=source_context
        )

    async def explain(self, key: str, user_id: str = "default_user") -> dict[str, Any]:
        """Explains why a preference is held, where it originated, and its confidence."""
        return await self.preference_engine.explain_preference(key=key, user_id=user_id)

    async def revert(self, key: str, user_id: str = "default_user") -> bool:
        """Reverts or disables a learned or set preference."""
        return await self.preference_engine.revert_preference(key=key, user_id=user_id)

    async def assemble_context(
        self,
        query: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
        working_turns: list[dict[str, str]] | None = None,
        raw_facts: list[dict[str, Any]] | None = None,
    ) -> AssembledPersonalContext:
        """Assembles ranked, budgeted, and sanitized context payload (<5ms)."""
        return await self.context_engine.assemble_context(
            query=query,
            session_id=session_id,
            user_id=user_id,
            working_turns=working_turns,
            raw_facts=raw_facts,
        )

    async def adapt_response(
        self,
        base_text: str,
        user_id: str = "default_user",
        detected_language: str | None = None,
    ) -> str:
        """Adapts response formatting, brevity, tone, and Hinglish code-switching."""
        prefs = await self.get_preferences(user_id=user_id)
        return AdaptiveResponseStrategy.adapt_response(
            base_message=base_text,
            preferences=prefs,
            detected_language=detected_language,
        )

    async def handle_turn_learning(
        self,
        user_utterance: str,
        session_id: str,
        previous_assistant_response: str | None = None,
        user_id: str = "default_user",
    ) -> UserCorrectionEvent | None:
        """Evaluates conversational turn for user corrections and updates preferences."""
        # 1. Inspect for malicious prompt injection attempting to poison memory
        is_safe, _ = MemoryPoisoningDefense.inspect_memory_candidate(
            key="dialogue", value=user_utterance, provenance=f"turn:{session_id}"
        )
        if not is_safe:
            logger.warning("Suppressed learning from adversarial turn utterance")
            return None

        # 2. Check for user correction
        correction = await self.correction_learner.detect_and_apply_correction(
            user_utterance=user_utterance,
            session_id=session_id,
            previous_assistant_response=previous_assistant_response,
            user_id=user_id,
        )
        return correction

    async def register_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 1,
        active_project_path: str | None = None,
        tags: list[str] | None = None,
        user_id: str = "default_user",
    ) -> PersonalGoal:
        """Registers an overarching personal goal."""
        return await self.goal_tracker.create_or_update_goal(
            title=title,
            description=description,
            priority=priority,
            active_project_path=active_project_path,
            tags=tags,
            user_id=user_id,
        )

    async def register_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        aliases: list[str] | None = None,
        context_metadata: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> PersonalEntity:
        """Registers a personal alias, nickname, or project entity."""
        return await self.entity_resolver.register_entity(
            canonical_name=canonical_name,
            entity_type=entity_type,
            aliases=aliases,
            context_metadata=context_metadata,
            user_id=user_id,
        )

    async def resolve_entity(
        self,
        token: str,
        expected_type: EntityType | None = None,
        user_id: str = "default_user",
    ) -> EntityResolutionResult:
        """Resolves token against personal vocabulary with zero-guessing on ambiguity."""
        return await self.entity_resolver.resolve_entity(
            token=token, expected_type=expected_type, user_id=user_id
        )

    async def observe_habit(
        self,
        action_name: str,
        parameters: dict[str, Any],
        trigger_context: str = "manual",
        user_id: str = "default_user",
    ) -> HabitPattern:
        """Records behavioral pattern as OBSERVED."""
        return await self.habit_engine.observe_action(
            action_name=action_name,
            parameters=parameters,
            trigger_context=trigger_context,
            user_id=user_id,
        )

    async def approve_habit_to_routine(
        self,
        habit_id: str,
        user_id: str = "default_user",
        routine_name: str | None = None,
    ) -> UserRoutine:
        """Converts user-approved habit into an active routine."""
        return await self.habit_engine.approve_habit_to_routine(
            habit_id=habit_id, user_id=user_id, routine_name=routine_name
        )

    async def generate_proactive_suggestion(
        self,
        trigger_type: ProactiveTriggerType,
        headline: str,
        action: str,
        parameters: dict[str, Any],
        reasoning: str,
        user_id: str = "default_user",
    ) -> ProactiveActionSuggestion | None:
        """Generates proactive suggestion under anti-annoyance limits."""
        return await self.habit_engine.generate_proactive_suggestion(
            trigger_type=trigger_type,
            headline=headline,
            action=action,
            parameters=parameters,
            reasoning=reasoning,
            user_id=user_id,
        )

    async def create_sync_delta(
        self, origin_device_id: str, user_id: str = "default_user"
    ) -> PersonalContextSyncDelta:
        """Creates cryptographically signed sync delta for cross-device mesh propagation."""
        return await self.sync_manager.create_sync_delta(
            origin_device_id=origin_device_id, user_id=user_id
        )

    async def apply_sync_delta(
        self, delta: PersonalContextSyncDelta, receiving_device_id: str = "pixel-local"
    ) -> bool:
        """Applies received sync delta with conflict resolution and revocation verification."""
        return await self.sync_manager.apply_sync_delta(
            delta=delta, receiving_device_id=receiving_device_id
        )

    async def purge_user_memory(self, user_id: str, keyword: str | None = None) -> int:
        """Right-to-Forget cascade across UserModel, goals, routines, habits, and entities."""
        purged = await self.store.purge_user_data(user_id=user_id, keyword=keyword)
        logger.info("Purged %d records in Personalization layer for user %s", purged, user_id)
        return purged
