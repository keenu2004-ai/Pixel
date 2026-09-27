"""Hostile Security and Invariant Verification Suite for Phase 9 Autonomous Workflows."""

from typing import Any

import pytest

from packages.contracts.autonomous import (
    AutonomousEvent,
    AutonomousTaskContract,
    EventFilter,
    ExecutionBudget,
    GoalContract,
    TaskLifecycleState,
)
from packages.contracts.tools import RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.agent_runtime.verifier import ActionVerifier
from services.autonomous.budget_manager import BudgetManager
from services.autonomous.drift_detector import GoalDriftDetector
from services.autonomous.engine import AutonomousWorkflowEngine
from services.autonomous.event_bus import EventBus
from services.autonomous.governor import TaskGovernor
from services.autonomous.notifications import TaskNotificationManager
from services.autonomous.scheduler import AutonomousScheduler


class MockDeleteTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="delete_all_files",
            description="Destroys directory contents",
            parameters_schema={},
            risk_class=RiskClass.HIGH_IMPACT,
            requires_approval=True,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(success=True, output={"deleted": True})


class MockCommandTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="execute_system_command",
            description="Runs shell command on host",
            parameters_schema={},
            risk_class=RiskClass.HIGH_IMPACT,
            requires_approval=True,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(success=True, output={"output": "ok"})


@pytest.fixture
def autonomous_harness() -> dict[str, Any]:
    scheduler = AutonomousScheduler(db_path=":memory:")
    budget_manager = BudgetManager(db_path=":memory:")
    drift_detector = GoalDriftDetector()
    governor = TaskGovernor(max_concurrent_tasks=5)
    notif_manager = TaskNotificationManager()
    policy_gate = AgentPolicyGate()
    tool_registry = ToolRegistry()
    action_verifier = ActionVerifier()

    engine = AutonomousWorkflowEngine(
        scheduler=scheduler,
        budget_manager=budget_manager,
        drift_detector=drift_detector,
        governor=governor,
        notification_manager=notif_manager,
        policy_gate=policy_gate,
        tool_registry=tool_registry,
        action_verifier=action_verifier,
    )

    return {
        "scheduler": scheduler,
        "budget_manager": budget_manager,
        "drift_detector": drift_detector,
        "governor": governor,
        "notif_manager": notif_manager,
        "policy_gate": policy_gate,
        "tool_registry": tool_registry,
        "engine": engine,
    }


@pytest.mark.asyncio
async def test_invariant_cancelled_task_cannot_restart(autonomous_harness: dict[str, Any]) -> None:
    engine: AutonomousWorkflowEngine = autonomous_harness["engine"]

    task = AutonomousTaskContract(
        task_id="task_cancel_sec",
        goal=GoalContract(objective="Background scan"),
        budget=ExecutionBudget(max_steps=10),
    )
    await engine.submit_task(task)
    await engine.cancel_task("task_cancel_sec")

    # Attempt to execute cancelled task
    state = await engine.execute_task_segment("task_cancel_sec", max_steps=2)
    assert state == TaskLifecycleState.CANCELLED


@pytest.mark.asyncio
async def test_invariant_budget_breach_strictly_halts_execution(
    autonomous_harness: dict[str, Any],
) -> None:
    engine: AutonomousWorkflowEngine = autonomous_harness["engine"]

    task = AutonomousTaskContract(
        task_id="task_budget_sec",
        goal=GoalContract(objective="Run memory test"),
        budget=ExecutionBudget(max_steps=2),  # only 2 steps allowed
    )
    await engine.submit_task(task)

    # First segment with 2 steps consumes full budget
    await engine.execute_task_segment("task_budget_sec", max_steps=2)

    # Attempt to run more steps must result in BUDGET_EXCEEDED
    state2 = await engine.execute_task_segment("task_budget_sec", max_steps=1)
    assert state2 == TaskLifecycleState.BUDGET_EXCEEDED


@pytest.mark.asyncio
async def test_invariant_goal_drift_triggers_pause_and_escalation(
    autonomous_harness: dict[str, Any],
) -> None:
    engine: AutonomousWorkflowEngine = autonomous_harness["engine"]
    tool_registry: ToolRegistry = autonomous_harness["tool_registry"]

    # Register an unauthorized destructive tool
    tool_registry.register_tool(MockDeleteTool())

    task = AutonomousTaskContract(
        task_id="task_drift_sec",
        goal=GoalContract(
            objective="Monitor build output",
            allowed_targets=["logs/build.log"],
            prohibited_actions=["delete", "drop"],
        ),
        allowed_tools=["delete_all_files"],  # Attempt to run prohibited action
        budget=ExecutionBudget(max_steps=10),
    )
    await engine.submit_task(task)

    state = await engine.execute_task_segment("task_drift_sec", max_steps=1)
    assert state == TaskLifecycleState.DRIFT_DETECTED

    retrieved = autonomous_harness["scheduler"].get_task("task_drift_sec")
    assert retrieved is not None
    assert retrieved.is_paused


@pytest.mark.asyncio
async def test_invariant_local_llm_cannot_bypass_l6_approval(
    autonomous_harness: dict[str, Any],
) -> None:
    engine: AutonomousWorkflowEngine = autonomous_harness["engine"]
    tool_registry: ToolRegistry = autonomous_harness["tool_registry"]

    # Register high-risk tool that requires user approval
    tool_registry.register_tool(MockCommandTool())

    task = AutonomousTaskContract(
        task_id="task_l6_sec",
        goal=GoalContract(objective="Deploy system patch"),
        allowed_tools=["execute_system_command"],
        budget=ExecutionBudget(max_steps=10),
    )
    await engine.submit_task(task)

    # Engine must halt and wait for user approval card
    state = await engine.execute_task_segment("task_l6_sec", max_steps=1)
    assert state == TaskLifecycleState.AWAITING_APPROVAL


@pytest.mark.asyncio
async def test_invariant_event_deduplication_prevents_duplicate_runs() -> None:
    event_bus = EventBus(deduplication_window_seconds=60.0)
    invocation_count = 0

    async def counting_subscriber(evt: AutonomousEvent) -> None:
        nonlocal invocation_count
        invocation_count += 1

    event_bus.subscribe("counter_sub", EventFilter(event_type_pattern="*"), counting_subscriber)

    evt = AutonomousEvent(
        event_id="evt_replay_01",
        event_type="cloud.build_finished",
        source="ci_bot",
        correlation_id="corr_replay",
        idempotency_key="unique_build_hash_789",
    )

    # Publish 5 duplicate events
    for _ in range(5):
        await event_bus.publish(evt)

    # Only 1 execution should have taken place
    assert invocation_count == 1
