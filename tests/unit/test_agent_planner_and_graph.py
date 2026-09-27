"""Unit tests for AgentPlanner and AgentGraph execution engine."""

import tempfile
from pathlib import Path
from typing import Any

import pytest

from packages.contracts.agent import AgentExecutionStatus
from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer
from services.agent_runtime.engine import AgentRuntimeEngine
from services.agent_runtime.planner import AgentPlanner


class MockSensitiveTool(BaseTool):
    """Tool that strictly requires user confirmation."""
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="format_disk",
            description="High risk disk format",
            risk_class=RiskClass.HIGH_IMPACT,
            requires_approval=True,
            parameters_schema={"type": "object", "properties": {"drive": {"type": "string"}}},
            audit_level=AuditLevel.CRYPTOGRAPHIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(success=True, output="Drive formatted.")


@pytest.fixture
def agent_engine() -> AgentRuntimeEngine:
    temp_cp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    checkpointer = SQLiteCheckpointer(db_path=temp_cp_db)
    engine = AgentRuntimeEngine(checkpointer=checkpointer)
    engine.tool_registry.register_tool(MockSensitiveTool())
    return engine


def test_agent_planner_formulate_plan() -> None:
    specs = [
        ToolSpec(name="search_knowledge", description="search", risk_class=RiskClass.READ, parameters_schema={}),
        ToolSpec(name="write_file", description="write", risk_class=RiskClass.REVERSIBLE_WRITE, parameters_schema={}),
    ]
    plan = AgentPlanner.formulate_plan(
        user_query="Find information about audio pipeline and save to audio_summary.txt",
        available_tools=specs,
    )

    assert len(plan.steps) == 2
    assert plan.steps[0].tool_name == "search_knowledge"
    assert plan.steps[1].tool_name == "write_file"
    assert plan.steps[1].arguments.get("path") == "audio_summary.txt"
    assert plan.steps[1].dependencies == [1]


@pytest.mark.asyncio
async def test_agent_graph_execution_success(agent_engine: AgentRuntimeEngine) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        out_file = Path(tmpdir) / "output.txt"
        query = f"write content to {out_file}"

        state = await agent_engine.execute_task(
            user_query=query,
            session_id="s_test_graph",
            user_id="u_test_graph",
        )

        assert state.status == AgentExecutionStatus.SUCCESS
        assert state.final_response is not None
        assert "Done!" in state.final_response
        assert out_file.exists()


@pytest.mark.asyncio
async def test_agent_graph_approval_pause_and_resume(agent_engine: AgentRuntimeEngine) -> None:
    query = "format disk C:"
    state = await agent_engine.execute_task(
        user_query=query,
        session_id="s_approval_test",
        user_id="u_approval_test",
    )

    # 1. Verify task paused awaiting approval
    assert state.status == AgentExecutionStatus.AWAITING_APPROVAL
    assert state.pending_approval is not None
    assert state.pending_approval.tool_name == "format_disk"
    token = state.pending_approval.confirmation_token

    # 2. Resume with user approval
    resumed_state = await agent_engine.resume_approval(
        task_id=state.task_id,
        confirmation_token=token,
        user_approved=True,
    )

    assert resumed_state is not None
    assert resumed_state.status == AgentExecutionStatus.SUCCESS
    assert "Done!" in str(resumed_state.final_response)


@pytest.mark.asyncio
async def test_agent_graph_approval_rejection(agent_engine: AgentRuntimeEngine) -> None:
    query = "format disk D:"
    state = await agent_engine.execute_task(
        user_query=query,
        session_id="s_reject_test",
        user_id="u_reject_test",
    )

    assert state.status == AgentExecutionStatus.AWAITING_APPROVAL
    assert state.pending_approval is not None
    token = state.pending_approval.confirmation_token

    # User rejects
    resumed_state = await agent_engine.resume_approval(
        task_id=state.task_id,
        confirmation_token=token,
        user_approved=False,
    )

    assert resumed_state is not None
    assert resumed_state.status == AgentExecutionStatus.POLICY_DENIED
    assert "rejected" in str(resumed_state.final_response).lower()
