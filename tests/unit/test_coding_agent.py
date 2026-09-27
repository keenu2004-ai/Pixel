"""Unit tests for CodingAgent autonomous refactoring, testing, and rollback."""

from pathlib import Path

import pytest

from packages.contracts.agent import AgentExecutionStatus
from services.coding.coding_agent import CodingAgent
from services.coding.serena_bridge import SerenaBridge
from services.coding.test_runner import IsolatedTestRunner


@pytest.mark.asyncio
async def test_coding_agent_successful_patch_and_verify(tmp_path: Path) -> None:
    # Set up a target file with a bug
    code_file = tmp_path / "calculator.py"
    code_file.write_text("def add(a, b):\n    return a - b  # Bug!\n", encoding="utf-8")

    # Set up unit test for calculator
    test_file = tmp_path / "test_calc.py"
    test_file.write_text("from calculator import add\ndef test_add(): assert add(2, 3) == 5\n", encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)
    test_runner = IsolatedTestRunner(workspace_root=tmp_path)
    agent = CodingAgent(bridge=bridge, test_runner=test_runner, workspace_root=tmp_path)

    # Correct patch
    fixed_code = "def add(a, b):\n    return a + b\n"
    state = await agent.execute_task(
        user_query="Fix addition bug in calculator.py",
        target_file="calculator.py",
        new_content=fixed_code,
        test_target="test_calc.py",
    )

    assert state.status == AgentExecutionStatus.SUCCESS
    assert state.plan is not None
    assert state.plan.is_complete is True
    assert state.last_verification is not None
    assert state.last_verification.is_verified is True
    assert code_file.read_text(encoding="utf-8") == fixed_code


@pytest.mark.asyncio
async def test_coding_agent_failed_tests_triggers_auto_rollback(tmp_path: Path) -> None:
    # Set up original code
    code_file = tmp_path / "math_util.py"
    original_code = "def multiply(a, b):\n    return a * b\n"
    code_file.write_text(original_code, encoding="utf-8")

    # Set up test expecting multiplication
    test_file = tmp_path / "test_math.py"
    test_file.write_text("from math_util import multiply\ndef test_mul(): assert multiply(2, 3) == 6\n", encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)
    test_runner = IsolatedTestRunner(workspace_root=tmp_path)
    agent = CodingAgent(bridge=bridge, test_runner=test_runner, workspace_root=tmp_path)

    # Bad patch that breaks the test
    broken_patch = "def multiply(a, b):\n    return a + b\n"
    state = await agent.execute_task(
        user_query="Modify multiply logic",
        target_file="math_util.py",
        new_content=broken_patch,
        test_target="test_math.py",
    )

    # Agent should detect verification failure and auto-rollback to original code
    assert state.status == AgentExecutionStatus.FAILED
    assert "Verification tests failed" in (state.error or "")
    assert code_file.read_text(encoding="utf-8") == original_code
