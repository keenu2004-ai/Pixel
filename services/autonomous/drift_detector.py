"""Goal drift detector for autonomous workflows to prevent unauthorized scope expansion."""

import logging
import re
from datetime import UTC, datetime
from typing import Any

from packages.contracts.autonomous import DriftReport, GoalContract
from packages.core.interfaces.autonomous import BaseDriftDetector

logger = logging.getLogger(__name__)


class GoalDriftDetector(BaseDriftDetector):
    """Evaluates agent execution plans and tool arguments against immutable goal contracts."""

    def evaluate_drift(
        self,
        goal: GoalContract,
        active_plan: list[dict[str, Any]],
        proposed_tools: list[str],
        proposed_targets: list[str],
        current_objective: str | None = None,
    ) -> DriftReport:
        """Evaluate if proposed actions violate authorized goal scope or prohibited actions."""
        unauthorized_targets: list[str] = []
        unauthorized_tools: list[str] = []
        objective_diverged = False
        reasons: list[str] = []

        # 1. Target Scope Check
        if goal.allowed_targets:
            for target in proposed_targets:
                normalized_target = target.strip().lower()
                matched = any(
                    self._target_matches(allowed.strip().lower(), normalized_target)
                    for allowed in goal.allowed_targets
                )
                if not matched:
                    unauthorized_targets.append(target)
                    reasons.append(
                        f"Target '{target}' is not in allowed targets: {goal.allowed_targets}"
                    )

        # 2. Prohibited Actions & Tools Check
        for tool in proposed_tools:
            for prohibited in goal.prohibited_actions:
                if prohibited.lower() in tool.lower():
                    unauthorized_tools.append(tool)
                    reasons.append(f"Tool '{tool}' matches prohibited action '{prohibited}'")

        # Check plan steps for prohibited keywords
        for step in active_plan:
            desc = str(step.get("description", "")).lower()
            for prohibited in goal.prohibited_actions:
                if re.search(r"\b" + re.escape(prohibited.lower()) + r"\b", desc):
                    reasons.append(f"Plan step '{desc}' contains prohibited action '{prohibited}'")

        # 3. Objective Divergence Check
        if current_objective and goal.objective:
            divergence = self._compute_objective_divergence(goal.objective, current_objective)
            if divergence > 0.6:
                objective_diverged = True
                reasons.append(
                    f"Objective diverged significantly from canonical goal (divergence: {divergence:.2f})"
                )

        # 4. Composite Divergence Score Calculation
        divergence_score = 0.0
        if unauthorized_targets:
            divergence_score += 0.4 * min(len(unauthorized_targets), 2)
        if unauthorized_tools:
            divergence_score += 0.5 * min(len(unauthorized_tools), 2)
        if objective_diverged:
            divergence_score += 0.6

        divergence_score = min(1.0, divergence_score)
        is_drifted = (
            divergence_score >= 0.5 or bool(unauthorized_targets) or bool(unauthorized_tools)
        )

        final_reason = (
            "; ".join(reasons)
            if reasons
            else "No drift detected: actions aligned with goal contract."
        )

        if is_drifted:
            logger.warning(
                "Goal drift detected! Divergence: %.2f. Reasons: %s", divergence_score, final_reason
            )

        return DriftReport(
            is_drifted=is_drifted,
            divergence_score=divergence_score,
            reason=final_reason,
            unauthorized_targets=unauthorized_targets,
            unauthorized_tools=unauthorized_tools,
            objective_divergence=objective_diverged,
            checked_at=datetime.now(UTC),
        )

    def _target_matches(self, pattern: str, target: str) -> bool:
        """Check if target matches pattern (supports wildcard * and substring paths)."""
        if pattern == "*" or pattern == target:
            return True
        if pattern.endswith("/*") and target.startswith(pattern[:-2]):
            return True
        if pattern in target:
            return True
        return False

    def _compute_objective_divergence(self, canonical: str, current: str) -> float:
        """Compute heuristic Jaccard word distance between canonical and proposed objectives."""
        words_canonical = set(re.findall(r"\w+", canonical.lower()))
        words_current = set(re.findall(r"\w+", current.lower()))

        if not words_canonical or not words_current:
            return 1.0

        intersection = words_canonical.intersection(words_current)
        union = words_canonical.union(words_current)

        similarity = len(intersection) / len(union)
        return 1.0 - similarity
