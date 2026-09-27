"""Unit tests for Agent State Contracts and SQLite Checkpointing."""

import tempfile
from datetime import UTC, datetime

import pytest

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
    PlanStep,
    TaskPlan,
)
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer


@pytest.fixture
def temp_checkpoint_db() -> str:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        return f.name


@pytest.fixture
def checkpointer(temp_checkpoint_db: str) -> SQLiteCheckpointer:
    return SQLiteCheckpointer(db_path=temp_checkpoint_db)


def test_agent_state_model_serialization() -> None:
    plan = TaskPlan(
        goal="Test goal",
        steps=[
            PlanStep(step_id=1, description="Step 1", tool_name="read_file", arguments={"path": "a.txt"}),
            PlanStep(step_id=2, description="Step 2", tool_name="write_file", arguments={"path": "b.txt", "content": "hello"}, dependencies=[1]),
        ],
    )
    state = AgentState(
        task_id="task_123",
        session_id="sess_123",
        user_query="Run test task",
        plan=plan,
        status=AgentExecutionStatus.EXECUTING,
    )

    json_str = state.model_dump_json()
    assert "task_123" in json_str
    assert "read_file" in json_str

    deserialized = AgentState.model_validate_json(json_str)
    assert deserialized.task_id == "task_123"
    assert deserialized.plan is not None
    assert len(deserialized.plan.steps) == 2
    assert deserialized.plan.steps[1].dependencies == [1]


@pytest.mark.asyncio
async def test_sqlite_checkpoint_save_and_restore(checkpointer: SQLiteCheckpointer) -> None:
    state = AgentState(
        task_id="task_abc",
        session_id="sess_abc",
        user_query="Compile code and report errors",
        status=AgentExecutionStatus.PLANNING,
    )

    # 1. Save checkpoint
    cp_id = await checkpointer.save_checkpoint(state)
    assert cp_id is not None

    # 2. Retrieve latest
    restored = await checkpointer.get_latest_checkpoint("task_abc")
    assert restored is not None
    assert restored.task_id == "task_abc"
    assert restored.status == AgentExecutionStatus.PLANNING

    # 3. Update state and save new checkpoint
    restored.status = AgentExecutionStatus.SUCCESS
    restored.updated_at = datetime.now(UTC)
    await checkpointer.save_checkpoint(restored)

    latest = await checkpointer.get_latest_checkpoint("task_abc")
    assert latest is not None
    assert latest.status == AgentExecutionStatus.SUCCESS

    # 4. List checkpoints
    history = await checkpointer.list_checkpoints("task_abc")
    assert len(history) == 2

    # 5. Delete checkpoints
    deleted = await checkpointer.delete_checkpoints("task_abc")
    assert deleted is True
    assert await checkpointer.get_latest_checkpoint("task_abc") is None
