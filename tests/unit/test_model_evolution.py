"""Unit tests for Dataset Lineage, Differential Privacy, Model Evaluator, Distillation, and Model Registry."""

import pytest

from packages.contracts.evolution import (
    EvolutionModelLifecycleState,
    TrainingConsentStatus,
)
from services.evolution.models.differential_privacy import DifferentialPrivacyAccountant
from services.evolution.models.distillation import ProgressiveDistillationEngine
from services.evolution.models.evaluator import ModelSafetyEvaluator
from services.evolution.models.lineage import DatasetLineageTracker
from services.evolution.models.registry import EvolutionModelRegistry


def test_dataset_lineage_and_consent_revocation() -> None:
    tracker = DatasetLineageTracker()

    tracker.record_interaction("int-1", "user-1", TrainingConsentStatus.CONSENT_GRANTED)
    tracker.record_interaction("int-2", "user-1", TrainingConsentStatus.CONSENT_GRANTED)
    tracker.record_interaction("int-3", "user-2", TrainingConsentStatus.CONSENT_GRANTED)

    assert len(tracker.get_eligible_training_samples("v1")) == 3

    # Revoke consent for user-1 (Right to be Forgotten)
    revoked = tracker.revoke_user_consent("user-1")
    assert revoked == 2

    # Eligible samples now only contains user-2
    eligible = tracker.get_eligible_training_samples("v1")
    assert len(eligible) == 1
    assert eligible[0].user_id == "user-2"


def test_differential_privacy_accountant() -> None:
    accountant = DifferentialPrivacyAccountant(epsilon_max=1.0, delta_max=1e-5)

    # Add Gaussian noise
    noisy_val = accountant.add_gaussian_noise(10.0, sensitivity=1.0, epsilon=0.4, delta=1e-6)
    assert isinstance(noisy_val, float)
    assert accountant.budget.epsilon_consumed == 0.4

    # Add Laplace noise
    noisy_laplace = accountant.add_laplace_noise(20.0, sensitivity=1.0, epsilon=0.5)
    assert isinstance(noisy_laplace, float)
    assert accountant.budget.epsilon_consumed == 0.9

    # Exceed budget -> PermissionError
    with pytest.raises(PermissionError, match="Differential privacy budget exhausted"):
        accountant.add_laplace_noise(30.0, sensitivity=1.0, epsilon=0.3)


def test_model_evaluator_and_registry_lifecycle() -> None:
    evaluator = ModelSafetyEvaluator()
    registry = EvolutionModelRegistry(evaluator=evaluator)

    # 1. Register model
    model_meta = registry.register_model(
        model_id="qwen-0.5b-distilled-v1",
        model_family="qwen",
        weights_digest_sha256="sha256_mock_hash",
    )
    assert model_meta["state"] == EvolutionModelLifecycleState.DISCOVERED

    # 2. Evaluate model
    metric = evaluator.evaluate_model(
        model_id="qwen-0.5b-distilled-v1",
        model_family="qwen",
        benchmark_accuracy=0.92,
        hallucination_score=0.02,
        policy_compliance_rate=1.0,
        injection_resistance_score=0.98,
        latency_p95_ms=120.0,
        memory_vram_mb=1024.0,
    )
    assert metric.is_regression_free is True

    # 3. Link evaluation
    assert registry.link_evaluation("qwen-0.5b-distilled-v1", metric) is True
    m1 = registry.get_model("qwen-0.5b-distilled-v1")
    assert m1 is not None
    assert m1["state"] == EvolutionModelLifecycleState.VERIFIED

    # 4. Promote to Candidate
    assert registry.promote_to_candidate("qwen-0.5b-distilled-v1") is True

    # 5. Promote to Canary
    promo = registry.promote_to_canary("qwen-0.5b-distilled-v1", canary_percent=10)
    assert promo.is_promoted is True
    m2 = registry.get_model("qwen-0.5b-distilled-v1")
    assert m2 is not None
    assert m2["state"] == EvolutionModelLifecycleState.CANARY

    # 6. Promote to Active
    assert registry.promote_to_active("qwen-0.5b-distilled-v1") is True
    assert registry.get_active_model_id() == "qwen-0.5b-distilled-v1"
    m3 = registry.get_model("qwen-0.5b-distilled-v1")
    assert m3 is not None
    assert m3["state"] == EvolutionModelLifecycleState.ACTIVE

    # 7. Rollback
    assert registry.rollback_model("qwen-0.5b-distilled-v1") is True
    assert registry.get_active_model_id() is None
    m4 = registry.get_model("qwen-0.5b-distilled-v1")
    assert m4 is not None
    assert m4["state"] == EvolutionModelLifecycleState.ROLLED_BACK


def test_progressive_distillation_engine() -> None:
    engine = ProgressiveDistillationEngine(min_accuracy_retention=0.88)

    run = engine.record_distillation_run(
        teacher_model_id="llama-3.2-3b",
        student_model_id="llama-3.2-1b",
        dataset_revision="v1",
        loss_final=0.08,
        accuracy_retention=0.94,
        compression_ratio=3.0,
    )
    assert run.status == "COMPLETED"
    assert len(engine.list_successful_runs()) == 1
