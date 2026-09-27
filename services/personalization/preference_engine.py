"""PIXEL — Preference Engine & Conflict Resolver.

Provides structured preference management, explicit vs inferred segregation,
conflict resolution (explicit supersedes inferred, newer supersedes older),
explainability ("Why do you think that?"), and reversibility.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.personalization import (
    ConfidenceTier,
    PersonalMemoryRecord,
    ProvenanceType,
    UserPreferenceProfile,
)
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class PreferenceEngine:
    """Core engine for user preferences, conflict resolution, and explainability."""

    def __init__(self, user_model_store: UserModelStore) -> None:
        self.store = user_model_store
        self._audit_trail: list[dict[str, Any]] = []

    async def get_preference_profile(self, user_id: str = "default_user") -> UserPreferenceProfile:
        """Retrieves active user preference profile."""
        user_model = await self.store.get_user_model(user_id=user_id)
        return user_model.preferences

    async def set_explicit_preference(
        self,
        key: str,
        value: Any,
        user_id: str = "default_user",
        source_context: str = "explicit_user_statement",
    ) -> PersonalMemoryRecord:
        """Sets an explicit preference from direct user instruction (Confidence 1.0, USER_CONFIRMED)."""
        record = PersonalMemoryRecord(
            user_id=user_id,
            key=key,
            value=value,
            provenance=ProvenanceType.EXPLICIT_USER,
            source_context=source_context,
            confidence=1.0,
            confidence_tier=ConfidenceTier.USER_CONFIRMED,
            last_confirmed_at=datetime.now(UTC),
        )

        user_model = await self.store.get_user_model(user_id=user_id)
        # Apply to typed profile if known attribute
        if hasattr(user_model.preferences, key):
            setattr(user_model.preferences, key, value)
        else:
            user_model.preferences.custom_preferences[key] = value
        user_model.preferences.updated_at = datetime.now(UTC)

        await self.store.save_user_model(user_model)

        self._audit_trail.append(
            {
                "action": "SET_EXPLICIT_PREFERENCE",
                "user_id": user_id,
                "key": key,
                "value": value,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        logger.info("Explicit preference set: %s = %s for user %s", key, value, user_id)
        return record

    async def record_inferred_preference(
        self,
        key: str,
        value: Any,
        confidence: float,
        user_id: str = "default_user",
        source_context: str = "behavioral_observation",
    ) -> PersonalMemoryRecord | None:
        """Records an inferred preference candidate.

        CRITICAL POLICY: Inferred preferences NEVER overwrite explicit user preferences.
        """
        user_model = await self.store.get_user_model(user_id=user_id)

        # Check if an explicit preference already exists for this key
        current_val = getattr(user_model.preferences, key, None)
        if current_val is None:
            current_val = user_model.preferences.custom_preferences.get(key)

        # If user explicitly set it, deny inferred override
        if current_val is not None and key in user_model.preferences.custom_preferences:
            logger.info(
                "Skipping inferred preference [%s=%s] because explicit preference exists [%s]",
                key,
                value,
                current_val,
            )
            return None

        tier = (
            ConfidenceTier.HIGH
            if confidence >= 0.8
            else ConfidenceTier.MEDIUM
            if confidence >= 0.5
            else ConfidenceTier.LOW
        )

        record = PersonalMemoryRecord(
            user_id=user_id,
            key=key,
            value=value,
            provenance=ProvenanceType.INFERRED,
            source_context=source_context,
            confidence=confidence,
            confidence_tier=tier,
        )

        # Only apply high-confidence inferences to active custom preferences
        if confidence >= 0.8:
            user_model.preferences.custom_preferences[f"inferred.{key}"] = value
            await self.store.save_user_model(user_model)

        return record

    async def explain_preference(self, key: str, user_id: str = "default_user") -> dict[str, Any]:
        """Provides full explainability and provenance for a preference."""
        user_model = await self.store.get_user_model(user_id=user_id)

        val = getattr(user_model.preferences, key, None)
        if val is None:
            val = user_model.preferences.custom_preferences.get(key)

        if val is None and f"inferred.{key}" in user_model.preferences.custom_preferences:
            val = user_model.preferences.custom_preferences[f"inferred.{key}"]
            return {
                "key": key,
                "value": val,
                "status": "INFERRED",
                "provenance": "Observed interaction patterns",
                "confidence": 0.8,
                "is_explicit": False,
                "can_revert": True,
                "explanation": f"I observed that you frequently use {val} based on past sessions.",
            }

        if val is not None:
            return {
                "key": key,
                "value": val,
                "status": "ACTIVE_EXPLICIT",
                "provenance": "User direct configuration / dialogue",
                "confidence": 1.0,
                "is_explicit": True,
                "can_revert": True,
                "explanation": f"You explicitly specified that your preference for '{key}' is '{val}'.",
            }

        return {
            "key": key,
            "value": None,
            "status": "NOT_SET",
            "explanation": f"No preference recorded for '{key}'. Using system defaults.",
        }

    async def revert_preference(self, key: str, user_id: str = "default_user") -> bool:
        """Reverts or removes a user preference (reversibility guarantee)."""
        user_model = await self.store.get_user_model(user_id=user_id)
        modified = False

        if key in user_model.preferences.custom_preferences:
            del user_model.preferences.custom_preferences[key]
            modified = True

        if f"inferred.{key}" in user_model.preferences.custom_preferences:
            del user_model.preferences.custom_preferences[f"inferred.{key}"]
            modified = True

        if modified:
            await self.store.save_user_model(user_model)
            logger.info("Reverted preference '%s' for user %s", key, user_id)
            return True
        return False
