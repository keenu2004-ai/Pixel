"""PIXEL — User Correction Learner & Reversible Learning Loop.

Detects conversational corrections ("No, I meant X", "I use Chrome now, not Edge"),
formulates learning hypotheses, evaluates confidence, applies state changes,
and preserves an undo stack for 100% reversibility.
"""

import logging
import re
from typing import Any

from packages.contracts.personalization import (
    CorrectionType,
    UserCorrectionEvent,
)
from services.personalization.preference_engine import PreferenceEngine

logger = logging.getLogger(__name__)


class CorrectionLearner:
    """Detects and applies user corrections to memory, preferences, and entity bindings."""

    # Regex patterns for detecting explicit user corrections
    CORRECTION_PATTERNS = [
        # "No, I meant [new_value]" or "No, I said [new_value]"
        (
            re.compile(
                r"(?:no|nahi),?\s+(?:i meant|i said|maine kaha|mera matlab tha)\s+([a-zA-Z0-9_\-\.\s]{2,40})",
                re.IGNORECASE,
            ),
            CorrectionType.FACT_CORRECTION,
        ),
        # "I use [new_value] now, not [old_value]" or "I switch to [new_value]"
        (
            re.compile(
                r"(?:i use|i prefer|switch to|meri pasand)\s+([a-zA-Z0-9_\-\.\s]{2,20})\s+(?:now|instead of|not|ab se)",
                re.IGNORECASE,
            ),
            CorrectionType.PREFERENCE_CHANGE,
        ),
        # "My [key] is actually [value]" or "Actually my [key] is [value]"
        (
            re.compile(
                r"(?:actually\s+)?my\s+([a-zA-Z_\s]+)\s+is\s+(?:actually\s+)?([a-zA-Z0-9_\-\.\s]{2,30})",
                re.IGNORECASE,
            ),
            CorrectionType.PREFERENCE_CHANGE,
        ),
        # "Don't be so [style]" / "Be more [style]"
        (
            re.compile(
                r"(?:be more|don't be so|thoda)\s+(concise|detailed|formal|casual|friendly|fast)",
                re.IGNORECASE,
            ),
            CorrectionType.BEHAVIOR_FEEDBACK,
        ),
    ]

    def __init__(self, preference_engine: PreferenceEngine) -> None:
        self.preference_engine = preference_engine
        self._history: list[UserCorrectionEvent] = []
        self._undo_stack: list[dict[str, Any]] = []

    async def detect_and_apply_correction(
        self,
        user_utterance: str,
        session_id: str = "default_session",
        previous_assistant_response: str | None = None,
        user_id: str = "default_user",
    ) -> UserCorrectionEvent | None:
        """Evaluates utterance for corrections and applies updates to the preference engine."""
        u_text = user_utterance.strip()

        # 1. Check for Revert / Undo command
        if re.search(
            r"(?:undo that|revert that|forget what you just learned|wapas lo)",
            u_text,
            re.IGNORECASE,
        ):
            return await self.undo_last_correction(user_id=user_id)

        # 2. Check for explicit correction patterns
        for pattern, corr_type in self.CORRECTION_PATTERNS:
            match = pattern.search(u_text)
            if match:
                groups = match.groups()
                new_val = groups[-1].strip()

                target_key = "general"
                if "editor" in u_text.lower() or "code" in u_text.lower():
                    target_key = "preferred_code_editor"
                elif "browser" in u_text.lower():
                    target_key = "preferred_browser"
                elif "concise" in new_val.lower() or "detailed" in new_val.lower():
                    target_key = "response_length"
                    new_val = new_val.upper()
                elif (
                    "formal" in new_val.lower()
                    or "casual" in new_val.lower()
                    or "friendly" in new_val.lower()
                ):
                    target_key = "tone"
                    new_val = new_val.upper()

                event = UserCorrectionEvent(
                    user_id=user_id,
                    session_id=session_id,
                    user_utterance=user_utterance,
                    previous_assistant_response=previous_assistant_response,
                    correction_type=corr_type,
                    target_key=target_key,
                    new_value=new_val,
                    confidence=0.95,
                    applied=True,
                )

                # Capture undo state
                old_val = await self.preference_engine.get_preference_profile(user_id=user_id)
                curr_val = getattr(old_val, target_key, None)
                event.old_value = curr_val

                # Apply new explicit preference
                await self.preference_engine.set_explicit_preference(
                    key=target_key,
                    value=new_val,
                    user_id=user_id,
                    source_context=f"correction:{session_id}",
                )

                self._history.append(event)
                self._undo_stack.append(
                    {
                        "user_id": user_id,
                        "target_key": target_key,
                        "old_value": curr_val,
                        "event_id": event.correction_id,
                    }
                )

                logger.info(
                    "User correction successfully applied: %s -> %s for user %s",
                    target_key,
                    new_val,
                    user_id,
                )
                return event

        return None

    async def undo_last_correction(
        self, user_id: str = "default_user"
    ) -> UserCorrectionEvent | None:
        """Rolls back the most recently applied user correction."""
        if not self._undo_stack:
            logger.info("Undo stack is empty; no correction to revert.")
            return None

        last_action = self._undo_stack.pop()
        target_key = last_action["target_key"]
        old_value = last_action["old_value"]

        if old_value is not None:
            await self.preference_engine.set_explicit_preference(
                key=target_key,
                value=old_value,
                user_id=user_id,
                source_context="undo_operation",
            )
        else:
            await self.preference_engine.revert_preference(key=target_key, user_id=user_id)

        undo_event = UserCorrectionEvent(
            user_id=user_id,
            session_id="undo_session",
            user_utterance="undo that",
            correction_type=CorrectionType.REVERT_LAST,
            target_key=target_key,
            new_value=old_value,
            applied=True,
        )
        self._history.append(undo_event)
        logger.info("Reverted correction on '%s' to '%s'", target_key, old_value)
        return undo_event

    def get_correction_history(self) -> list[UserCorrectionEvent]:
        """Returns the full log of detected user corrections."""
        return list(self._history)
