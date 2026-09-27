"""PIXEL — Phase 16 UI Grounding & Zero-Guess Target Resolution.

Resolves human and agent requests ("Click Settings", "Ye submit button dabao")
to precise on-screen coordinates without guessing.
"""

import re

from packages.contracts.multimodal import (
    ScreenSemanticModel,
    UIElement,
    UIElementType,
    VisualActionTarget,
)
from services.multimodal.providers.base import BaseUIUnderstandingProvider


class UIGroundingEngine:
    """Grounds user intents to verified UI element coordinates."""

    def __init__(
        self,
        provider: BaseUIUnderstandingProvider | None = None,
        confidence_threshold: float = 0.70,
    ) -> None:
        self._provider = provider
        self._confidence_threshold = confidence_threshold

    def _normalize_query(self, query: str) -> str:
        """Strips conversational fillers, Hinglish verbs, and punctuation."""
        q = query.lower().strip()
        # Remove English/Hinglish action wrappers
        patterns = [
            r"^(click\s+(on\s+)?(the\s+)?)",
            r"^(press\s+(the\s+)?)",
            r"^(select\s+(the\s+)?)",
            r"^(open\s+(the\s+)?)",
            r"^(dabao\s+)",
            r"^(kholo\s+)",
            r"(\s+pe\s+click\s+karo)$",
            r"(\s+ko\s+click\s+karo)$",
            r"(\s+dabao)$",
            r"(\s+kholo)$",
            r"(\s+button)$",
            r"(\s+icon)$",
            r"(\s+tab)$",
            r"(\s+link)$",
        ]
        for pat in patterns:
            q = re.sub(pat, "", q).strip()
        return q

    async def ground_target(
        self,
        screen_model: ScreenSemanticModel,
        user_intent: str,
        element_type_filter: UIElementType | None = None,
    ) -> VisualActionTarget | None:
        """Locates the target element with strict anti-guessing guarantees."""
        if self._provider:
            return await self._provider.ground_element(
                screen_model,
                user_intent,
                element_type_filter.value if element_type_filter else None,
            )

        target_name = self._normalize_query(user_intent)
        if not target_name:
            return None

        exact_matches: list[UIElement] = []
        partial_matches: list[UIElement] = []

        for element in screen_model.elements:
            if element_type_filter and element.element_type != element_type_filter:
                continue

            label_norm = element.label.lower().strip()

            if label_norm == target_name:
                exact_matches.append(element)
            elif target_name in label_norm or label_norm in target_name:
                partial_matches.append(element)

        candidates = exact_matches if exact_matches else partial_matches

        if not candidates:
            return None

        if len(candidates) > 1:
            # Rule 22: NEVER CLICK BY GUESS — Multiple matching elements -> Ask for clarification
            first = candidates[0]
            cx, cy = first.bounding_box.center_point()
            return VisualActionTarget(
                element_id=first.element_id,
                label=first.label,
                element_type=first.element_type,
                target_coordinates=(cx, cy),
                confidence=0.5,
                is_ambiguous=True,
                candidate_matches_count=len(candidates),
            )

        target = candidates[0]
        if target.confidence < self._confidence_threshold:
            # Confidence too low -> do not act
            return None

        cx, cy = target.bounding_box.center_point()
        return VisualActionTarget(
            element_id=target.element_id,
            label=target.label,
            element_type=target.element_type,
            target_coordinates=(cx, cy),
            confidence=target.confidence,
            is_ambiguous=False,
            candidate_matches_count=1,
        )
