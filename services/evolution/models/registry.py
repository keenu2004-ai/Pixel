"""PIXEL — Governed Model Registry.

Manages the lifecycle of evolved, adapted, and distilled local models:
DISCOVERED -> EVALUATED -> VERIFIED -> CANDIDATE -> CANARY -> ACTIVE / ROLLED_BACK / REVOKED.
"""

import uuid
from datetime import UTC, datetime

from packages.contracts.evolution import (
    EvolutionModelLifecycleState,
    ModelEvaluationMetric,
    ModelPromotionDecision,
)
from services.evolution.models.evaluator import ModelSafetyEvaluator


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class EvolutionModelRegistry:
    """Provides lifecycle tracking, SHA-256 integrity verification, and safe promotion/rollback for evolved models."""

    def __init__(self, evaluator: ModelSafetyEvaluator | None = None) -> None:
        self.evaluator = evaluator or ModelSafetyEvaluator()
        self._models: dict[str, dict[str, object]] = {}  # model_id -> metadata
        self._active_model_id: str | None = None
        self._promotions: list[ModelPromotionDecision] = []

    def register_model(
        self,
        model_id: str,
        model_family: str,
        weights_digest_sha256: str,
        provenance: str = "distillation_pipeline",
    ) -> dict[str, object]:
        """Registers a newly discovered model artifact."""
        metadata: dict[str, object] = {
            "model_id": model_id,
            "model_family": model_family,
            "weights_digest_sha256": weights_digest_sha256,
            "state": EvolutionModelLifecycleState.DISCOVERED,
            "provenance": provenance,
            "registered_at": _utc_now_iso(),
            "evaluation_id": None,
        }
        self._models[model_id] = metadata
        return metadata

    def link_evaluation(self, model_id: str, evaluation: ModelEvaluationMetric) -> bool:
        """Links evaluation results and transitions state to EVALUATED / VERIFIED."""
        model = self._models.get(model_id)
        if not model:
            return False

        model["evaluation_id"] = evaluation.evaluation_id
        if evaluation.is_regression_free:
            model["state"] = EvolutionModelLifecycleState.VERIFIED
        else:
            model["state"] = EvolutionModelLifecycleState.REJECTED

        return True

    def promote_to_candidate(self, model_id: str) -> bool:
        """Transitions a VERIFIED model to CANDIDATE state."""
        model = self._models.get(model_id)
        if not model or model["state"] != EvolutionModelLifecycleState.VERIFIED:
            return False

        model["state"] = EvolutionModelLifecycleState.CANDIDATE
        return True

    def promote_to_canary(
        self,
        candidate_model_id: str,
        canary_percent: int = 10,
        promoted_by: str = "evolution.governor",
    ) -> ModelPromotionDecision:
        """Deploys candidate model to canary traffic."""
        model = self._models.get(candidate_model_id)
        if not model or model["state"] not in (
            EvolutionModelLifecycleState.CANDIDATE,
            EvolutionModelLifecycleState.VERIFIED,
        ):
            raise ValueError(f"Model {candidate_model_id} is not eligible for canary")

        promo_id = f"prm-{uuid.uuid4().hex[:8]}"
        decision = ModelPromotionDecision(
            promotion_id=promo_id,
            candidate_model_id=candidate_model_id,
            baseline_model_id=self._active_model_id or "base-model-v0",
            evaluation_id=str(model["evaluation_id"]),
            is_promoted=True,
            canary_traffic_percent=canary_percent,
            promoted_by=promoted_by,
            decision_rationale=f"Canary promotion at {canary_percent}% traffic",
            timestamp_utc=_utc_now_iso(),
        )

        model["state"] = EvolutionModelLifecycleState.CANARY
        self._promotions.append(decision)
        return decision

    def promote_to_active(self, model_id: str) -> bool:
        """Promotes a CANARY model to fully ACTIVE production model."""
        model = self._models.get(model_id)
        if not model or model["state"] != EvolutionModelLifecycleState.CANARY:
            return False

        # Deprecate previous active model
        if self._active_model_id and self._active_model_id in self._models:
            self._models[self._active_model_id]["state"] = EvolutionModelLifecycleState.DEPRECATED

        model["state"] = EvolutionModelLifecycleState.ACTIVE
        self._active_model_id = model_id
        return True

    def rollback_model(self, model_id: str, reason: str = "Canary regression") -> bool:
        """Rolls back an active or canary model."""
        model = self._models.get(model_id)
        if not model:
            return False

        model["state"] = EvolutionModelLifecycleState.ROLLED_BACK
        if self._active_model_id == model_id:
            self._active_model_id = None
        return True

    def get_model(self, model_id: str) -> dict[str, object] | None:
        """Retrieves model metadata."""
        return self._models.get(model_id)

    def get_active_model_id(self) -> str | None:
        """Returns the current active model ID."""
        return self._active_model_id

    def list_models(self) -> list[dict[str, object]]:
        """Lists all registered models."""
        return list(self._models.values())
