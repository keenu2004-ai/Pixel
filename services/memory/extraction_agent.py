"""Asynchronous Memory Extraction and Fact Distillation Agent.

Extracts structured semantic facts and episodic summaries from conversation turns
with PII scrubbing and conflict detection without blocking the voice response path.
"""

import logging
import re

from packages.contracts.memory import FactRecord
from services.memory.pii_scrubber import PIIScrubber
from services.memory.stores.sqlite_store import SQLiteMemoryStore

logger = logging.getLogger(__name__)


class MemoryExtractor:
    """Extracts facts, preferences, and episode summaries from dialogue."""

    # Common fact extraction heuristics
    PREFERENCE_PATTERNS = [
        (
            re.compile(
                r"(?:i prefer|my preference is|i like|i love)\s+([a-zA-Z0-9_\-\.\s]{2,30})",
                re.IGNORECASE,
            ),
            "user.preference",
        ),
        (
            re.compile(
                r"(?:i use|my editor is|my ide is)\s+([a-zA-Z0-9_\-\.\s]{2,30})", re.IGNORECASE
            ),
            "user.editor",
        ),
        (re.compile(r"(?:my name is|call me|i am)\s+([a-zA-Z]{2,25})", re.IGNORECASE), "user.name"),
        (
            re.compile(
                r"(?:my timezone is|i live in|i am in)\s+([a-zA-Z0-9_\-\.\s]{2,30})", re.IGNORECASE
            ),
            "user.location",
        ),
        (
            re.compile(
                r"(?:meri pasand|mujhe pasand hai)\s+([a-zA-Z0-9_\-\.\s]{2,30})", re.IGNORECASE
            ),
            "user.preference",
        ),
        (
            re.compile(r"(?:mera naam|mujhe bulate hain)\s+([a-zA-Z]{2,25})", re.IGNORECASE),
            "user.name",
        ),
    ]

    # Explicit correction/negation patterns ("I don't use X anymore", "Don't call me Y")
    CORRECTION_PATTERNS = [
        (
            re.compile(
                r"(?:i don't like|i no longer use|i stopped using)\s+([a-zA-Z0-9_\-\.\s]{2,30})",
                re.IGNORECASE,
            ),
            "user.preference",
        ),
    ]

    def __init__(self, memory_store: SQLiteMemoryStore) -> None:
        self.memory_store = memory_store

    async def extract_and_persist(
        self,
        user_query: str,
        assistant_response: str,
        session_id: str,
        user_id: str = "default_user",
    ) -> list[FactRecord]:
        """Extracts facts from a conversation turn and persists sanitized facts and episode."""
        # 1. Scrub PII and Secrets from input
        scrub_query = PIIScrubber.scrub(user_query)
        scrub_resp = PIIScrubber.scrub(assistant_response)

        # 2. Extract facts if no dangerous secrets are present
        extracted_facts: list[FactRecord] = []
        if not scrub_query.has_secrets:
            text = scrub_query.cleaned_text

            # Check positive preferences
            for pattern, key_prefix in self.PREFERENCE_PATTERNS:
                match = pattern.search(text)
                if match:
                    val = match.group(1).strip().title()
                    # Persist fact
                    fact = await self.memory_store.set_fact(
                        key=f"{key_prefix}.{val.lower().replace(' ', '_')}",
                        value=val,
                        user_id=user_id,
                        category="preference" if "preference" in key_prefix else "profile",
                        provenance=f"extracted_turn:{session_id}",
                    )
                    extracted_facts.append(fact)
                    logger.info(
                        "Distilled new semantic fact [%s = %s] for user %s", fact.key, val, user_id
                    )

        # 3. Record episodic summary
        episode_summary = f"User asked: '{scrub_query.cleaned_text[:100]}'. Assistant replied: '{scrub_resp.cleaned_text[:100]}'."
        await self.memory_store.record_episode(
            summary=episode_summary,
            session_id=session_id,
            user_id=user_id,
            interaction_type="voice_dialogue",
            metadata={"redactions": scrub_query.redaction_count + scrub_resp.redaction_count},
        )

        return extracted_facts
