"""PIXEL — Multi-Turn Conversational Context & Ambiguity Resolver.

Manages conversational state across turns:
- Ambiguity detection (e.g. "Call Rahul" when 2 Rahuls exist -> prompts user without guessing)
- Multi-turn reference resolution (e.g. "Open VS Code" -> "Open the PIXEL project")
- Conversational control actions ("Do that again", "Cancel that", "Forget what I just said")
"""

import logging
from typing import Any

from packages.contracts.mobile import AndroidContact

logger = logging.getLogger("pixel.intent_engine.conversational_context")


class AmbiguityException(Exception):
    """Raised when an action is ambiguous and requires explicit user clarification."""

    pass


class ConversationalContextManager:
    """Tracks multi-turn dialog context and handles disambiguation."""

    def __init__(self) -> None:
        self._recent_turns: list[dict[str, str]] = []
        self._last_executed_action: dict[str, Any] | None = None
        self._last_app_opened: str | None = None

    def record_turn(self, user_query: str, assistant_response: str) -> None:
        """Records conversational turn in active short-term context."""
        self._recent_turns.append(
            {"user_query": user_query, "assistant_response": assistant_response}
        )
        if len(self._recent_turns) > 20:
            self._recent_turns.pop(0)

    def record_action(self, action_name: str, parameters: dict[str, Any]) -> None:
        """Records successful action for 'do that again' support."""
        self._last_executed_action = {"action": action_name, "parameters": parameters}
        if "app_name" in parameters:
            self._last_app_opened = str(parameters["app_name"])

    def resolve_contact_ambiguity(
        self, query_name: str, matching_contacts: list[AndroidContact]
    ) -> AndroidContact:
        """Resolves contact or prompts user clarification if multiple matches exist."""
        if not matching_contacts:
            raise ValueError(f"No contact found matching '{query_name}'.")

        if len(matching_contacts) == 1:
            return matching_contacts[0]

        # Ambiguity detected: NEVER guess among multiple contacts
        candidate_names = [f"{c.display_name} ({c.phone_number})" for c in matching_contacts]
        prompt_msg = (
            f"Multiple contacts found for '{query_name}': {', '.join(candidate_names)}. "
            "Which one would you like to choose?"
        )
        logger.warning("Ambiguity detected for contact query '%s': %s", query_name, candidate_names)
        raise AmbiguityException(prompt_msg)

    def handle_conversational_commands(self, user_query: str) -> dict[str, Any] | None:
        """Evaluates special conversational commands like 'cancel', 'repeat', 'forget'."""
        normalized = user_query.strip().lower()

        if normalized in ("cancel that", "stop", "abort", "cancel"):
            logger.info("Conversational cancellation command detected")
            return {
                "command": "CANCEL",
                "message": "Cancelled.",
            }

        elif normalized in ("do that again", "repeat that", "again"):
            if not self._last_executed_action:
                return {
                    "command": "REPEAT_UNAVAILABLE",
                    "message": "There is no previous action to repeat.",
                }
            logger.info("Repeating previous action: %s", self._last_executed_action)
            return {
                "command": "REPEAT",
                "action": self._last_executed_action["action"],
                "parameters": self._last_executed_action["parameters"],
                "message": f"Repeating {self._last_executed_action['action']}.",
            }

        elif normalized in ("forget what i just said", "forget last turn", "clear recent memory"):
            if self._recent_turns:
                popped = self._recent_turns.pop()
                logger.info("Purged recent conversational turn: %s", popped)
            return {
                "command": "FORGET_RECENT",
                "message": "I have forgotten what you just said.",
            }

        return None

    def get_last_contextual_app(self) -> str | None:
        """Returns the most recently focused application in conversational context."""
        return self._last_app_opened
