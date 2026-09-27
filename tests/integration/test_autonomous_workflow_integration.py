"""Integration tests for autonomous workflows, event triggers, checkpointing, and execution."""

from typing import Any

import pytest

from packages.contracts.autonomous import (
    AutonomousEvent,
    AutonomousTaskContract,
    EventFilter,
    ExecutionBudget,
    GoalContract,
    NotificationPolicy,
    ScheduleType,
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


class MockSystemStatusTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_system_status",
            description="Reads current CPU and memory status",
            parameters_schema={},
            risk_class=RiskClass.READ,
            requires_approval=False,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(
            success=True,
            output={"status": "ok", "cpu_percent": 12.0},
        )


@pytest.mark.asyncio
async def test_end_to_end_autonomous_workflow() -> None:
    event_bus = EventBus()
    scheduler = AutonomousScheduler(db_path=":memory:")
    budget_manager = BudgetManager(db_path=":memory:")
    drift_detector = GoalDriftDetector()
    governor = TaskGovernor(max_concurrent_tasks=5)
    notif_manager = TaskNotificationManager()
    policy_gate = AgentPolicyGate()
    tool_registry = ToolRegistry()
    action_verifier = ActionVerifier()

    # Register an allowed low-risk tool in registry
    tool_registry.register_tool(MockSystemStatusTool())

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

    # 1. Event trigger wiring
    async def on_device_status(event: AutonomousEvent) -> None:
        task = AutonomousTaskContract(
            task_id=f"task_triggered_{event.event_id}",
            user_id="user_admin",
            goal=GoalContract(
                objective="Monitor system status",
                allowed_targets=["system/*"],
                prohibited_actions=["delete", "reboot"],
            ),
            schedule_type=ScheduleType.ONE_SHOT,
            budget=ExecutionBudget(max_steps=5, max_tool_calls=5),
            notification_policy=NotificationPolicy(notify_on_start=True, notify_on_complete=True),
            allowed_tools=["read_system_status"],
        )
        await engine.submit_task(task)

    event_bus.subscribe("device_sub", EventFilter(event_type_pattern="device.*"), on_device_status)

    # Publish triggering event
    trigger_event = AutonomousEvent(
        event_id="evt_dev_100",
        event_type="device.status",
        source="server_node",
        correlation_id="corr_999",
    )
    await event_bus.publish(trigger_event)

    # Verify task was created and scheduled
    task_id = "task_triggered_evt_dev_100"
    created_task = scheduler.get_task(task_id)
    assert created_task is not None
    assert created_task.state == TaskLifecycleState.SCHEDULED

    # 2. Execute bounded segment
    final_state = await engine.execute_task_segment(task_id, max_steps=2)
    assert final_state == TaskLifecycleState.COMPLETED

    # 3. Checkpoint verification
    latest_checkpoint = engine.get_latest_checkpoint(task_id)
    assert latest_checkpoint is not None
    assert latest_checkpoint.verify_integrity()
    assert latest_checkpoint.budget.consumed_steps > 0

    # 4. Notifications emitted
    notifs = notif_manager.get_notifications_for_task(task_id)
    assert len(notifs) >= 2  # START and COMPLETE
