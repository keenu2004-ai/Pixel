"""PIXEL — Habit Detection, User-Governed Routines & Proactive Assistance Engine.

Enforces:
1. Pattern Detection is NOT Permission: Habits remain OBSERVED until user approves.
2. User-Governed Routines: Deterministic execution of morning, coding, and work routines.
3. Proactive Anti-Annoyance Limits: Rate limiting, cooldowns, and feedback learning.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.personalization import (
    HabitPattern,
    PatternStatus,
    ProactiveActionSuggestion,
    ProactiveBudgetState,
    ProactiveTriggerType,
    RoutineStep,
    UserRoutine,
)
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class HabitRoutineEngine:
    """Coordinates habit observation, routine lifecycle, and bounded proactive assistance."""

    def __init__(
        self,
        user_model_store: UserModelStore,
        default_cooldown_seconds: int = 300,
        max_daily_suggestions: int = 5,
    ) -> None:
        self.store = user_model_store
        self.budget_state: dict[str, ProactiveBudgetState] = {}
        self.default_cooldown = default_cooldown_seconds
        self.max_daily = max_daily_suggestions

    def _get_budget(self, user_id: str) -> ProactiveBudgetState:
        if user_id not in self.budget_state:
            self.budget_state[user_id] = ProactiveBudgetState(
                user_id=user_id,
                cooldown_seconds=self.default_cooldown,
            )
        return self.budget_state[user_id]

    async def observe_action(
        self,
        action_name: str,
        parameters: dict[str, Any],
        trigger_context: str = "manual",
        user_id: str = "default_user",
    ) -> HabitPattern:
        """Records an action occurrence and updates or creates an OBSERVED habit pattern."""
        user_model = await self.store.get_user_model(user_id=user_id)

        # Look for existing pattern matching this action and trigger
        matching = next(
            (
                h
                for h in user_model.habits
                if h.associated_action == action_name and h.trigger_condition == trigger_context
            ),
            None,
        )

        now = datetime.now(UTC)
        if matching:
            matching.occurrence_count += 1
            matching.last_observed_at = now
            matching.confidence = min(1.0, 0.4 + (0.1 * matching.occurrence_count))
            await self.store.save_habit(matching)
            logger.info(
                "Updated observed habit '%s' (count=%d, confidence=%.2f)",
                matching.name,
                matching.occurrence_count,
                matching.confidence,
            )
            return matching

        # Create new observed pattern
        new_pattern = HabitPattern(
            user_id=user_id,
            name=f"Pattern: {action_name} on {trigger_context}",
            description=f"User frequently executes '{action_name}' when '{trigger_context}' occurs.",
            trigger_condition=trigger_context,
            associated_action=action_name,
            action_parameters=parameters,
            occurrence_count=1,
            first_observed_at=now,
            last_observed_at=now,
            status=PatternStatus.OBSERVED,  # Strictly OBSERVED, never auto-approved!
            confidence=0.4,
        )
        await self.store.save_habit(new_pattern)
        return new_pattern

    async def approve_habit_to_routine(
        self,
        habit_id: str,
        user_id: str = "default_user",
        routine_name: str | None = None,
    ) -> UserRoutine:
        """User explicitly authorizes an observed habit, converting it into an active routine."""
        user_model = await self.store.get_user_model(user_id=user_id)
        habit = next((h for h in user_model.habits if h.habit_id == habit_id), None)
        if not habit:
            raise ValueError(f"Habit with ID '{habit_id}' not found.")

        habit.status = PatternStatus.USER_APPROVED
        await self.store.save_habit(habit)

        routine = UserRoutine(
            user_id=user_id,
            name=routine_name or f"Routine: {habit.associated_action}",
            steps=[
                RoutineStep(
                    step_id=1,
                    name=habit.associated_action,
                    tool_or_action=habit.associated_action,
                    parameters=habit.action_parameters,
                    requires_confirmation=False,
                )
            ],
            is_active=True,
        )
        await self.store.save_routine(routine)
        logger.info("Habit '%s' approved and converted to routine '%s'", habit.name, routine.name)
        return routine

    async def list_routines(self, user_id: str = "default_user") -> list[UserRoutine]:
        """Lists all registered routines for a user."""
        user_model = await self.store.get_user_model(user_id=user_id)
        return user_model.routines

    async def list_habits(self, user_id: str = "default_user") -> list[HabitPattern]:
        """Lists observed and approved habits for a user."""
        user_model = await self.store.get_user_model(user_id=user_id)
        return user_model.habits

    async def generate_proactive_suggestion(
        self,
        trigger_type: ProactiveTriggerType,
        headline: str,
        action: str,
        parameters: dict[str, Any],
        reasoning: str,
        user_id: str = "default_user",
    ) -> ProactiveActionSuggestion | None:
        """Evaluates whether to generate a proactive assistance suggestion under anti-annoyance limits."""
        user_model = await self.store.get_user_model(user_id=user_id)
        if not user_model.preferences.proactive_assistance_enabled:
            logger.info("Proactive assistance disabled in user preferences")
            return None

        budget = self._get_budget(user_id)
        now = datetime.now(UTC)

        # Check cooldown
        if budget.last_suggestion_timestamp:
            elapsed = (now - budget.last_suggestion_timestamp).total_seconds()
            if elapsed < budget.cooldown_seconds:
                logger.info(
                    "Proactive suggestion suppressed due to cooldown (%.1fs < %ds)",
                    elapsed,
                    budget.cooldown_seconds,
                )
                return None

        # Check daily limits
        if budget.daily_suggestions_count >= self.max_daily:
            logger.info("Proactive suggestion suppressed: daily limit reached (%d)", self.max_daily)
            return None

        # Record suggestion in budget
        budget.hourly_suggestions_count += 1
        budget.daily_suggestions_count += 1
        budget.last_suggestion_timestamp = now

        suggestion = ProactiveActionSuggestion(
            user_id=user_id,
            trigger_type=trigger_type,
            headline=headline,
            suggested_action=action,
            parameters=parameters,
            reasoning=reasoning,
        )
        logger.info("Proactive suggestion generated: %s -> %s", headline, action)
        return suggestion

    def record_proactive_feedback(
        self,
        user_id: str,
        accepted: bool,
        dismissed: bool = False,
    ) -> None:
        """Records user response to proactive suggestion to adjust future frequency."""
        budget = self._get_budget(user_id)
        if accepted:
            budget.accepted_count += 1
        elif dismissed:
            budget.dismissed_count += 1
            # If user frequently dismisses, increase cooldown
            budget.cooldown_seconds = min(1800, int(budget.cooldown_seconds * 1.5))
        else:
            budget.ignored_count += 1
