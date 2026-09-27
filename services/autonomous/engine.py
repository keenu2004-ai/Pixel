"""Autonomous workflow execution engine with bounded autonomy, checkpoints, and drift control."""

import logging
import time
import uuid
from datetime import UTC, datetime

from packages.contracts.autonomous import (
    AutonomousTaskContract,
    ExecutionBudget,
    ScheduleType,
    TaskCheckpoint,
    TaskLifecycleState,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from packages.core.interfaces.autonomous import BaseAutonomousEngine
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.agent_runtime.verifier import ActionVerifier
from services.autonomous.budget_manager import BudgetManager
from services.autonomous.drift_detector import GoalDriftDetector
from services.autonomous.governor import TaskGovernor
from services.autonomous.notifications import TaskNotificationManager
from services.autonomous.scheduler import AutonomousScheduler

logger = logging.getLogger(__name__)


class AutonomousWorkflowEngine(BaseAutonomousEngine):
    """Orchestrates bounded autonomous task execution, checkpointing, and goal drift defense."""

    def __init__(
        self,
        scheduler: AutonomousScheduler,
        budget_manager: BudgetManager,
        drift_detector: GoalDriftDetector,
        governor: TaskGovernor,
        notification_manager: TaskNotificationManager,
        policy_gate: AgentPolicyGate,
        tool_registry: ToolRegistry,
        action_verifier: ActionVerifier | None = None,
    ) -> None:
        self.scheduler = scheduler
        self.budget_manager = budget_manager
        self.drift_detector = drift_detector
        self.governor = governor
        self.notification_manager = notification_manager
        self.policy_gate = policy_gate
        self.tool_registry = tool_registry
        self.action_verifier = action_verifier or ActionVerifier()
        self._checkpoints: dict[str, list[TaskCheckpoint]] = {}

    async def submit_task(self, task: AutonomousTaskContract) -> str:
        """Register, persist, initialize budget, and schedule an autonomous task."""
        # Initialize persistent budget
        self.budget_manager.initialize_task_budget(task.task_id, task.budget)

        # Create initial checkpoint
        initial_checkpoint = TaskCheckpoint(
            checkpoint_id=f"chk_{uuid.uuid4().hex[:12]}",
            task_id=task.task_id,
            version=1,
            state=TaskLifecycleState.AUTHORIZED,
            budget=task.budget,
            active_plan=[],
            completed_steps=[],
            execution_evidence=[],
            created_at=datetime.now(UTC),
        )
        initial_checkpoint.checksum = initial_checkpoint.compute_checksum()
        self._checkpoints.setdefault(task.task_id, []).append(initial_checkpoint)
        task.current_checkpoint_id = initial_checkpoint.checkpoint_id
        task.state = TaskLifecycleState.SCHEDULED

        # Persist to scheduler
        self.scheduler.schedule_task(task)
        self.notification_manager.notify(
            task, "START", "Task Scheduled", f"Task '{task.task_id}' scheduled."
        )
        logger.info("Autonomous task '%s' submitted and scheduled.", task.task_id)
        return task.task_id

    async def execute_task_segment(self, task_id: str, max_steps: int = 5) -> TaskLifecycleState:
        """Execute a single bounded slice of an autonomous task."""
        task = self.scheduler.get_task(task_id)
        if not task:
            raise ValueError(f"Task '{task_id}' not found in scheduler.")

        # Invariant: Cancellation and Pause checks
        if task.is_cancelled or task.state == TaskLifecycleState.CANCELLED:
            logger.warning("Refusing to execute cancelled task '%s'", task_id)
            return TaskLifecycleState.CANCELLED

        if task.is_paused or task.state == TaskLifecycleState.PAUSED:
            logger.info("Task '%s' is paused.", task_id)
            return TaskLifecycleState.PAUSED

        # Acquire execution slot from governor
        slot_acquired = await self.governor.acquire_task_slot(task_id)
        if not slot_acquired:
            logger.warning("Task governor denied slot for '%s' due to capacity.", task_id)
            return task.state

        start_time = time.monotonic()
        task.state = TaskLifecycleState.RUNNING
        self.scheduler.update_task_state(task_id, TaskLifecycleState.RUNNING)

        try:
            # Re-read budget from persistent store
            current_budget = self.budget_manager.get_budget(task_id) or task.budget

            # Check if budget already exceeded
            is_breached, reason = current_budget.is_exceeded()
            if is_breached:
                task.state = TaskLifecycleState.BUDGET_EXCEEDED
                task.failure_reason = reason
                self.scheduler.update_task_state(task_id, TaskLifecycleState.BUDGET_EXCEEDED)
                self.notification_manager.notify(
                    task, "FAILURE", "Budget Exceeded", reason or "Budget breach"
                )
                return TaskLifecycleState.BUDGET_EXCEEDED

            # Execute bounded slice steps
            steps_executed = 0
            while steps_executed < max_steps:
                # 1. Budget check before step
                ok, updated_budget, breach_reason = self.budget_manager.record_step(
                    task_id=task_id,
                    steps=1,
                    tool_calls=0,
                    duration_seconds=time.monotonic() - start_time,
                    tokens=50,
                )
                if not ok:
                    task.state = TaskLifecycleState.BUDGET_EXCEEDED
                    task.failure_reason = breach_reason
                    self.scheduler.update_task_state(task_id, TaskLifecycleState.BUDGET_EXCEEDED)
                    self.notification_manager.notify(
                        task, "FAILURE", "Budget Exceeded", breach_reason or "Budget breach"
                    )
                    return TaskLifecycleState.BUDGET_EXCEEDED

                # 2. Check for tool permissions and goal drift
                active_tools = task.allowed_tools if task.allowed_tools else ["read_system_status"]
                drift_report = self.drift_detector.evaluate_drift(
                    goal=task.goal,
                    active_plan=[{"description": f"Autonomous step {steps_executed + 1}"}],
                    proposed_tools=active_tools,
                    proposed_targets=task.goal.allowed_targets,
                    current_objective=task.goal.objective,
                )

                if drift_report.is_drifted and task.drift_policy.pause_on_drift:
                    task.state = TaskLifecycleState.DRIFT_DETECTED
                    task.is_paused = True
                    task.failure_reason = drift_report.reason
                    self.scheduler.pause_task(task_id)
                    self.scheduler.update_task_state(task_id, TaskLifecycleState.DRIFT_DETECTED)
                    self._create_checkpoint(task, updated_budget, TaskLifecycleState.DRIFT_DETECTED)
                    self.notification_manager.notify(
                        task, "DRIFT", "Goal Drift Detected", drift_report.reason
                    )
                    return TaskLifecycleState.DRIFT_DETECTED

                # 3. Policy Gate Evaluation (L6)
                for tool_name in active_tools:
                    # Enforce tool allowlist
                    if task.allowed_tools and tool_name not in task.allowed_tools:
                        task.state = TaskLifecycleState.POLICY_DENIED
                        task.failure_reason = f"Tool '{tool_name}' not in task allowed tools."
                        self.scheduler.update_task_state(task_id, TaskLifecycleState.POLICY_DENIED)
                        return TaskLifecycleState.POLICY_DENIED

                    # Enforce prohibited tools
                    if tool_name in task.prohibited_tools or any(
                        p in tool_name for p in task.goal.prohibited_actions
                    ):
                        task.state = TaskLifecycleState.POLICY_DENIED
                        task.failure_reason = f"Tool '{tool_name}' is prohibited by goal contract."
                        self.scheduler.update_task_state(task_id, TaskLifecycleState.POLICY_DENIED)
                        return TaskLifecycleState.POLICY_DENIED

                    # Get tool spec from registry
                    tool_spec = self.tool_registry.get_tool_spec(tool_name)
                    if not tool_spec:
                        tool_spec = ToolSpec(
                            name=tool_name,
                            description=f"Autonomous tool {tool_name}",
                            parameters_schema={},
                            risk_class=RiskClass.READ,
                            requires_approval=False,
                        )

                    decision, approval_card = self.policy_gate.evaluate(
                        tool_spec=tool_spec,
                        arguments={},
                        task_id=task_id,
                        session_id=task.session_id,
                        user_id=task.user_id,
                    )

                    if decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION:
                        task.state = TaskLifecycleState.AWAITING_APPROVAL
                        self.scheduler.update_task_state(
                            task_id, TaskLifecycleState.AWAITING_APPROVAL
                        )
                        self._create_checkpoint(
                            task, updated_budget, TaskLifecycleState.AWAITING_APPROVAL
                        )
                        self.notification_manager.notify(
                            task,
                            "APPROVAL_REQUIRED",
                            "Approval Required",
                            f"Tool '{tool_name}' requires confirmation.",
                        )
                        return TaskLifecycleState.AWAITING_APPROVAL
                    elif decision.verdict == PolicyVerdict.DENY:
                        task.state = TaskLifecycleState.POLICY_DENIED
                        self.scheduler.update_task_state(task_id, TaskLifecycleState.POLICY_DENIED)
                        return TaskLifecycleState.POLICY_DENIED

                    # Record tool call in budget
                    self.budget_manager.record_step(task_id=task_id, steps=0, tool_calls=1)

                steps_executed += 1

            # Bounded segment completed -> emit checkpoint
            final_budget = self.budget_manager.get_budget(task_id) or task.budget
            self._create_checkpoint(task, final_budget, TaskLifecycleState.RUNNING)

            # Check if one-shot task completed
            if task.schedule_type == ScheduleType.ONE_SHOT:
                task.state = TaskLifecycleState.COMPLETED
                self.scheduler.update_task_state(task_id, TaskLifecycleState.COMPLETED)
                self.notification_manager.notify(
                    task,
                    "COMPLETE",
                    "Task Completed",
                    f"Autonomous task '{task_id}' finished successfully.",
                )
            else:
                task.state = TaskLifecycleState.SCHEDULED
                self.scheduler.update_task_state(task_id, TaskLifecycleState.SCHEDULED)

            return task.state

        finally:
            await self.governor.release_task_slot(task_id)

    def _create_checkpoint(
        self,
        task: AutonomousTaskContract,
        budget: ExecutionBudget,
        state: TaskLifecycleState,
    ) -> TaskCheckpoint:
        """Create, hash, and persist task checkpoint."""
        history = self._checkpoints.setdefault(task.task_id, [])
        version = len(history) + 1
        checkpoint = TaskCheckpoint(
            checkpoint_id=f"chk_{uuid.uuid4().hex[:12]}",
            task_id=task.task_id,
            version=version,
            state=state,
            budget=budget,
            active_plan=[],
            completed_steps=[],
            execution_evidence=[],
            created_at=datetime.now(UTC),
        )
        checkpoint.checksum = checkpoint.compute_checksum()
        history.append(checkpoint)
        task.current_checkpoint_id = checkpoint.checkpoint_id
        return checkpoint

    def get_latest_checkpoint(self, task_id: str) -> TaskCheckpoint | None:
        """Retrieve most recent checkpoint for a task."""
        history = self._checkpoints.get(task_id, [])
        return history[-1] if history else None

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel an autonomous task and release all resources."""
        await self.governor.release_task_slot(task_id)
        task = self.scheduler.get_task(task_id)
        if task:
            task.is_cancelled = True
            task.state = TaskLifecycleState.CANCELLED
            self.notification_manager.notify(
                task, "FAILURE", "Task Cancelled", f"Task '{task_id}' was cancelled."
            )
        return self.scheduler.cancel_task(task_id)

    async def pause_task(self, task_id: str) -> bool:
        """Pause task execution."""
        await self.governor.release_task_slot(task_id)
        return self.scheduler.pause_task(task_id)

    async def resume_task(self, task_id: str) -> bool:
        """Resume a paused task."""
        task = self.scheduler.get_task(task_id)
        if not task or task.is_cancelled:
            return False
        return self.scheduler.resume_task(task_id)
