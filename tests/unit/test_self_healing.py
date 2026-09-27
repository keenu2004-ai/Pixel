"""Unit tests for Self-Healing Orchestrator, Change Proposals, and Regression Test Generator."""

import tempfile

from packages.contracts.evolution import (
    ChangeProposalState,
    RemediationClass,
    RemediationProposal,
)
from services.evolution.healing.orchestrator import SelfHealingOrchestrator
from services.evolution.healing.proposals import ChangeProposalManager
from services.evolution.healing.regression_generator import RegressionTestGenerator


def test_regression_test_generator_valid() -> None:
    gen = RegressionTestGenerator()
    reg = gen.generate_test(
        target_module="services.memory.manager",
        test_function_name="test_memory_deduplication",
        setup_code="x = 10; y = 20",
        execution_code="res = x + y",
        assertion_code="assert res == 30",
    )
    assert reg.ast_valid is True
    assert reg.safety_checked is True
    assert "assert res == 30" in reg.test_code


def test_regression_test_generator_blocks_hostile_code() -> None:
    gen = RegressionTestGenerator()

    # Attempt to inject os.system
    hostile_code = """
import os
def test_hack():
    os.system("rm -rf /")
    assert True
"""
    valid, is_safe, violations = gen.validate_test_safety(hostile_code)
    assert valid is True
    assert is_safe is False
    assert any("Forbidden call" in v for v in violations)

    # Attempt to omit assertions
    no_assert = """
def test_noop():
    x = 10
"""
    valid, is_safe, violations = gen.validate_test_safety(no_assert)
    assert is_safe is False
    assert any("must contain at least one assert" in v for v in violations)


def test_change_proposal_lifecycle_and_self_healing() -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = f"{tmp_dir}/test_proposals.db"
        mgr = ChangeProposalManager(db_path=db_path)
        orchestrator = SelfHealingOrchestrator(proposal_manager=mgr)

        # Automatic remediation proposal
        prop = RemediationProposal(
            proposal_id="rem-001",
            anomaly_id="anom-001",
            hypothesis_id="hypo-001",
            remediation_class=RemediationClass.CLEAR_BOUNDED_CACHE,
            is_automatic_allowed=True,
            parameters={"target_cache": "query_cache"},
        )

        change = orchestrator.process_remediation(prop)
        assert change.state == ChangeProposalState.PROMOTED
        assert change.canary_percentage == 100

        # Verify persisted in database
        saved = mgr.get_proposal(change.proposal_id)
        assert saved is not None
        assert saved.state == ChangeProposalState.PROMOTED

        # Trigger rollback
        rolled_back = orchestrator.trigger_rollback(change.proposal_id, reason="Testing rollback")
        assert rolled_back is True
        saved_rb = mgr.get_proposal(change.proposal_id)
        assert saved_rb is not None
        assert saved_rb.state == ChangeProposalState.ROLLED_BACK
        assert saved_rb.canary_percentage == 0
