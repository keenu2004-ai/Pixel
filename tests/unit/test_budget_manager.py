"""Unit tests for BudgetManager persistence and consumption tracking."""

from packages.contracts.autonomous import ExecutionBudget
from services.autonomous.budget_manager import BudgetManager


def test_budget_manager_persistence_and_increments() -> None:
    bm = BudgetManager(db_path=":memory:")
    initial_budget = ExecutionBudget(max_steps=10, max_tool_calls=5, max_duration_seconds=60.0)

    bm.initialize_task_budget("task_b1", initial_budget)

    # Step 1
    ok, b_curr, reason = bm.record_step(
        task_id="task_b1", steps=3, tool_calls=2, duration_seconds=1.5
    )
    assert ok
    assert b_curr.consumed_steps == 3
    assert b_curr.consumed_tool_calls == 2
    assert b_curr.consumed_duration_seconds == 1.5

    # Step 2: breach tool call budget
    ok2, b_curr2, reason2 = bm.record_step(
        task_id="task_b1", steps=1, tool_calls=4, duration_seconds=1.0
    )
    assert not ok2
    assert b_curr2.consumed_tool_calls == 6
    assert "Tool call budget exceeded" in str(reason2)


def test_budget_manager_retrieval() -> None:
    bm = BudgetManager(db_path=":memory:")
    bm.initialize_task_budget("task_b2", ExecutionBudget(max_steps=50))

    retrieved = bm.get_budget("task_b2")
    assert retrieved is not None
    assert retrieved.max_steps == 50
    assert retrieved.consumed_steps == 0
