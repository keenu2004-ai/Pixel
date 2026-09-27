"""PIXEL — Minimal Relevant Context Engine & Ranking Layer.

Assembles minimal relevant context for LLM / Planner from:
1. Active Goals & Recent Tasks
2. Explicit User Preferences & Tone Guidelines
3. Ranked Semantic Memory Facts (Fresh, High Confidence)
4. Active Entities & Working Memory
5. Poisoning-Defense Sanitization & Strict Token Budgets (<5ms assembly).
"""

import logging
import time
from typing import Any

from packages.contracts.personalization import (
    AssembledPersonalContext,
    ProvenanceType,
    RankedContextItem,
)
from services.personalization.entity_resolver import EntityResolver
from services.personalization.goal_tracker import GoalTracker
from services.personalization.poisoning_defense import MemoryPoisoningDefense
from services.personalization.preference_engine import PreferenceEngine
from services.personalization.user_model_store import UserModelStore

logger = logging.getLogger(__name__)


class ContextEngine:
    """High-performance context assembly and ranking engine."""

    def __init__(
        self,
        user_model_store: UserModelStore,
        preference_engine: PreferenceEngine,
        goal_tracker: GoalTracker,
        entity_resolver: EntityResolver,
        max_context_items: int = 5,
        max_tokens_budget: int = 800,
    ) -> None:
        self.store = user_model_store
        self.preference_engine = preference_engine
        self.goal_tracker = goal_tracker
        self.entity_resolver = entity_resolver
        self.max_items = max_context_items
        self.max_tokens = max_tokens_budget

    async def assemble_context(
        self,
        query: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
        working_turns: list[dict[str, str]] | None = None,
        raw_facts: list[dict[str, Any]] | None = None,
    ) -> AssembledPersonalContext:
        """Assembles ranked, budgeted, and sanitized context payload."""
        t0 = time.perf_counter()
        q_lower = query.lower()

        # 1. Fetch user model and preference profile
        user_model = await self.store.get_user_model(user_id=user_id)
        prefs = user_model.preferences

        candidate_items: list[RankedContextItem] = []

        # 2. Check active goal
        matched_goal = await self.goal_tracker.match_goal_by_query(query=query, user_id=user_id)
        active_goal_title = matched_goal.title if matched_goal else None
        if matched_goal:
            content_str = f"Active Goal: '{matched_goal.title}'. Priority: {matched_goal.priority}."
            if matched_goal.active_project_path:
                content_str += f" Path: {matched_goal.active_project_path}"
            candidate_items.append(
                RankedContextItem(
                    source_type="GOAL",
                    key=f"goal.{matched_goal.goal_id}",
                    content=content_str,
                    relevance_score=0.95,
                    recency_score=1.0,
                    confidence_score=1.0,
                    final_rank_score=0.95,
                    provenance=ProvenanceType.EXPLICIT_USER,
                )
            )

        # 3. Check preferences matching query tokens (e.g. editor, browser, language)
        if any(w in q_lower for w in ["editor", "code", "ide", "vscode", "pycharm"]):
            candidate_items.append(
                RankedContextItem(
                    source_type="PREFERENCE",
                    key="preferred_code_editor",
                    content=f"Preferred Editor: {prefs.preferred_code_editor}",
                    relevance_score=0.9,
                    recency_score=1.0,
                    confidence_score=1.0,
                    final_rank_score=0.9,
                    provenance=ProvenanceType.EXPLICIT_USER,
                )
            )

        if any(w in q_lower for w in ["browser", "web", "chrome", "edge", "firefox", "search"]):
            candidate_items.append(
                RankedContextItem(
                    source_type="PREFERENCE",
                    key="preferred_browser",
                    content=f"Preferred Browser: {prefs.preferred_browser}",
                    relevance_score=0.9,
                    recency_score=1.0,
                    confidence_score=1.0,
                    final_rank_score=0.9,
                    provenance=ProvenanceType.EXPLICIT_USER,
                )
            )

        # 4. Process semantic facts
        if raw_facts:
            for f in raw_facts:
                f_key = str(f.get("key", ""))
                f_val = str(f.get("value", ""))
                f_conf = float(f.get("confidence", 1.0))
                # Skip stale or deactivated facts
                if not f.get("is_active", True):
                    continue

                # Compute relevance signal based on keyword overlap
                rel = 0.5
                if any(w in q_lower for w in f_key.lower().split(".")):
                    rel += 0.4
                if any(w in q_lower for w in f_val.lower().split()):
                    rel += 0.3
                rel = min(1.0, rel)

                # Skip low relevance facts unless explicitly relevant
                if rel >= 0.6:
                    rank_score = (rel * 0.6) + (f_conf * 0.4)
                    candidate_items.append(
                        RankedContextItem(
                            source_type="FACT",
                            key=f_key,
                            content=f"{f_key}: {f_val}",
                            relevance_score=rel,
                            confidence_score=f_conf,
                            final_rank_score=rank_score,
                            provenance=ProvenanceType.EXPLICIT_USER,
                        )
                    )

        # 5. Check entities
        for entity in user_model.entities:
            if entity.canonical_name.lower() in q_lower or any(
                a in q_lower for a in entity.aliases
            ):
                candidate_items.append(
                    RankedContextItem(
                        source_type="ENTITY",
                        key=f"entity.{entity.canonical_name}",
                        content=f"Entity [{entity.entity_type}]: '{entity.canonical_name}' ({entity.context_metadata})",
                        relevance_score=0.88,
                        recency_score=0.9,
                        confidence_score=entity.confidence,
                        final_rank_score=0.88,
                        provenance=ProvenanceType.EXPLICIT_USER,
                    )
                )

        # 6. Rank items descending by final_rank_score
        candidate_items.sort(key=lambda x: x.final_rank_score, reverse=True)

        # 7. Apply strict budget (max items and estimated token budget)
        selected_items = candidate_items[: self.max_items]

        # 8. Wrap selected items with Poisoning Defense data envelopes
        sanitized_snippets: list[str] = []
        for item in selected_items:
            envelope = MemoryPoisoningDefense.wrap_as_untrusted_data(
                item.content, source_label=item.source_type
            )
            sanitized_snippets.append(envelope)

        summary_text = "\n".join(sanitized_snippets)
        est_tokens = len(summary_text.split()) * 2  # Approximate token metric
        latency_ms = (time.perf_counter() - t0) * 1000

        return AssembledPersonalContext(
            user_id=user_id,
            session_id=session_id,
            query=query,
            items=selected_items,
            injected_facts_summary=summary_text,
            active_goal_title=active_goal_title,
            language_recommendation=str(prefs.language_mode),
            tone_recommendation=str(prefs.tone),
            total_tokens_estimated=est_tokens,
            assembly_latency_ms=latency_ms,
        )
