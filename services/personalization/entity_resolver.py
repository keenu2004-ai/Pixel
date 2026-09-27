"""PIXEL — Personal Vocabulary & User-Specific Entity Resolver.

Resolves person names, projects, repositories, devices, applications, and paths against
the user's personal context with ZERO-GUESSING on ambiguous matches (interactive clarification).
"""

import logging
from datetime import UTC, datetime
from typing import Any

from packages.contracts.personalization import (
    EntityResolutionResult,
    EntityType,
    PersonalEntity,
)
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class EntityResolver:
    """Resolves personal entities, nicknames, projects, and contacts."""

    def __init__(self, user_model_store: UserModelStore) -> None:
        self.store = user_model_store

    async def register_entity(
        self,
        canonical_name: str,
        entity_type: EntityType,
        aliases: list[str] | None = None,
        context_metadata: dict[str, Any] | None = None,
        user_id: str = "default_user",
    ) -> PersonalEntity:
        """Registers or updates a user-specific entity mapping."""
        user_model = await self.store.get_user_model(user_id=user_id)
        # Check existing by canonical name and type
        existing = next(
            (
                e
                for e in user_model.entities
                if e.canonical_name.lower() == canonical_name.lower()
                and e.entity_type == entity_type
            ),
            None,
        )

        all_aliases = [canonical_name.lower()]
        if aliases:
            all_aliases.extend([a.lower().strip() for a in aliases])

        now = datetime.now(UTC)
        if existing:
            existing.aliases = list(set(existing.aliases + all_aliases))
            if context_metadata:
                existing.context_metadata.update(context_metadata)
            existing.last_referenced_at = now
            await self.store.save_entity(existing)
            logger.info("Updated entity '%s' for user %s", canonical_name, user_id)
            return existing

        new_entity = PersonalEntity(
            user_id=user_id,
            entity_type=entity_type,
            canonical_name=canonical_name,
            aliases=list(set(all_aliases)),
            context_metadata=context_metadata or {},
            created_at=now,
            last_referenced_at=now,
        )
        await self.store.save_entity(new_entity)
        logger.info("Registered entity '%s' [%s] for user %s", canonical_name, entity_type, user_id)
        return new_entity

    async def resolve_entity(
        self,
        token: str,
        expected_type: EntityType | None = None,
        user_id: str = "default_user",
    ) -> EntityResolutionResult:
        """Resolves a token against known entities.

        CRITICAL REQUIREMENT: If multiple matching entities exist, NEVER GUESS.
        Return ambiguous=True with candidate options.
        """
        user_model = await self.store.get_user_model(user_id=user_id)
        token_clean = token.lower().strip().strip("'\"")

        candidates: list[PersonalEntity] = []
        for e in user_model.entities:
            if expected_type and e.entity_type != expected_type:
                continue

            # Check exact canonical or alias matches
            if token_clean == e.canonical_name.lower() or token_clean in [
                a.lower() for a in e.aliases
            ]:
                candidates.append(e)
            # Check token substring in canonical name
            elif token_clean in e.canonical_name.lower():
                candidates.append(e)

        if not candidates:
            return EntityResolutionResult(
                matched=False,
                ambiguous=False,
                query_term=token,
            )

        if len(candidates) == 1:
            match = candidates[0]
            match.last_referenced_at = datetime.now(UTC)
            await self.store.save_entity(match)
            return EntityResolutionResult(
                matched=True,
                ambiguous=False,
                query_term=token,
                resolved_entity=match,
                candidate_entities=candidates,
            )

        # Ambiguous match (e.g. Rahul Sharma @ work vs Rahul Verma @ tennis)
        candidate_labels = [
            f"{c.canonical_name} ({c.context_metadata.get('relationship', c.entity_type)})"
            for c in candidates
        ]
        clarification = (
            f"Multiple matches found for '{token}': {', '.join(candidate_labels)}. "
            "Which one did you mean?"
        )
        logger.warning("Ambiguous entity resolution for '%s': %s", token, candidate_labels)
        return EntityResolutionResult(
            matched=False,
            ambiguous=True,
            query_term=token,
            candidate_entities=candidates,
            clarification_prompt=clarification,
        )
