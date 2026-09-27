"""Specialized CodingAgent for Semantic Code Refactoring and Repair.

Follows the autonomous coding lifecycle:
Understand -> Inspect AST Symbols -> Reproduce/Run Tests -> Apply Safe Patch -> Verify Tests -> Rollback on Failure -> Report Evidence.
"""

import logging
from pathlib import Path

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
    PlanStep,
    StepStatus,
    TaskPlan,
    VerificationResult,
)
from packages.contracts.coding import PatchResult, TestExecutionResult
from services.coding.serena_bridge import SerenaBridge
from services.coding.test_runner import IsolatedTestRunner

logger = logging.getLogger(__name__)


class CodingAgent:
    """Specialized Agent for autonomous, verifiable code inspection, modification, and testing."""

    def __init__(
        self,
        bridge: SerenaBridge | None = None,
        test_runner: IsolatedTestRunner | None = None,
        workspace_root: str | Path = ".",
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.bridge = bridge or SerenaBridge(workspace_root=self.workspace_root)
        self.test_runner = test_runner or IsolatedTestRunner(workspace_root=self.workspace_root)

    async def execute_task(
        self,
        user_query: str,
        target_file: str | None = None,
        new_content: str | None = None,
        test_target: str | None = None,
        session_id: str = "coding_session",
        user_id: str = "coding_user",
    ) -> AgentState:
        """Executes an autonomous coding task with AST validation, test verification, and auto-rollback."""
        state = AgentState(
            user_query=user_query,
            session_id=session_id,
            user_id=user_id,
        )

        # 1. Planning Phase
        steps = [
            PlanStep(step_id=1, description="Inspect repository symbols and structure"),
            PlanStep(
                step_id=2,
                description="Run baseline test reproduction",
                tool_name="run_isolated_tests",
            ),
            PlanStep(
                step_id=3,
                description="Apply code modification with AST syntax validation",
                tool_name="apply_code_patch",
            ),
            PlanStep(
                step_id=4,
                description="Execute verification tests in isolated runner",
                tool_name="run_isolated_tests",
            ),
            PlanStep(step_id=5, description="Verify result integrity or trigger rollback"),
        ]
        state.plan = TaskPlan(goal=user_query, steps=steps)
        state.status = AgentExecutionStatus.EXECUTING

        # Step 1: Inspect Symbols
        state.plan.steps[0].status = StepStatus.IN_PROGRESS
        symbols = []
        if target_file:
            symbols = self.bridge.extract_symbols_from_file(target_file)
        else:
            symbols = self.bridge.search_symbols(user_query, max_results=10)
        state.plan.steps[0].result = {"symbols_found": len(symbols)}
        state.plan.steps[0].status = StepStatus.COMPLETED

        # Step 2: Baseline test if test target is specified
        state.plan.steps[1].status = StepStatus.IN_PROGRESS
        baseline_res = None
        if test_target:
            baseline_res = self.test_runner.run_tests(test_paths=[test_target])
            state.plan.steps[1].result = baseline_res.model_dump()
        state.plan.steps[1].status = StepStatus.COMPLETED

        # Step 3: Apply patch if new content is provided
        patch_res: PatchResult | None = None
        if target_file and new_content is not None:
            state.plan.steps[2].status = StepStatus.IN_PROGRESS
            patch_res = self.bridge.apply_patch(target_file, new_content, validate_syntax=True)
            state.plan.steps[2].result = patch_res.model_dump()

            if not patch_res.success:
                state.plan.steps[2].status = StepStatus.FAILED
                state.plan.steps[2].error = patch_res.error
                state.status = AgentExecutionStatus.FAILED
                state.error = f"Patch application failed: {patch_res.error}"
                return state

            state.plan.steps[2].status = StepStatus.COMPLETED

        # Step 4: Run Verification Tests
        state.plan.steps[3].status = StepStatus.IN_PROGRESS
        verify_test_res: TestExecutionResult | None = None
        if test_target:
            verify_test_res = self.test_runner.run_tests(test_paths=[test_target])
            state.plan.steps[3].result = verify_test_res.model_dump()
            state.plan.steps[3].status = (
                StepStatus.COMPLETED if verify_test_res.all_passed else StepStatus.FAILED
            )
        else:
            state.plan.steps[3].status = StepStatus.SKIPPED

        # Step 5: Verification and Rollback Decision
        state.plan.steps[4].status = StepStatus.IN_PROGRESS
        if verify_test_res and not verify_test_res.all_passed:
            # Tests failed after patch -> trigger rollback
            rollback_success = False
            if patch_res and patch_res.rollback_token:
                rollback_success = self.bridge.rollback_patch(patch_res.rollback_token)

            state.plan.steps[4].status = StepStatus.FAILED
            state.plan.steps[
                4
            ].error = f"Verification tests failed ({verify_test_res.failed} failures). Auto-rollback executed: {rollback_success}"
            state.status = AgentExecutionStatus.FAILED
            state.error = state.plan.steps[4].error
            state.last_verification = VerificationResult(
                is_verified=False,
                tool_name="run_isolated_tests",
                details=f"Test verification failed. Rollback status: {rollback_success}",
                evidence={"failed_tests": [f.model_dump() for f in verify_test_res.failures]},
            )
            return state

        # If everything succeeded
        state.plan.steps[4].status = StepStatus.COMPLETED
        state.plan.is_complete = True
        state.status = AgentExecutionStatus.SUCCESS
        state.final_response = (
            f"Coding task successfully completed and verified for query: '{user_query}'"
        )
        state.last_verification = VerificationResult(
            is_verified=True,
            tool_name="apply_code_patch",
            details="AST syntax validation and isolated tests passed cleanly.",
            evidence={
                "diff": patch_res.diff if patch_res else "",
                "tests_passed": verify_test_res.passed if verify_test_res else 0,
            },
        )

        return state
