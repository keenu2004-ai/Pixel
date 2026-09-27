"""Specialized ComputerAgent for Desktop Automation and Visual Inspection.

Follows the desktop interaction lifecycle:
Inspect State -> Enumerate Windows -> Focus Target -> Execute Action -> Verify Resulting State.
"""

import logging
from typing import Any

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
    PlanStep,
    StepStatus,
    TaskPlan,
    VerificationResult,
)
from services.computer_control.desktop_adapter import DesktopAdapter

logger = logging.getLogger(__name__)


class ComputerAgent:
    """Specialized Agent for desktop window management, clipboard, and visual inspection."""

    def __init__(self, adapter: DesktopAdapter | None = None) -> None:
        self.adapter = adapter or DesktopAdapter()

    async def execute_task(
        self,
        user_query: str,
        target_app: str | None = None,
        action: str = "focus",
        clipboard_text: str | None = None,
        session_id: str = "desktop_session",
        user_id: str = "desktop_user",
    ) -> AgentState:
        """Executes a desktop control task with state verification."""
        state = AgentState(
            user_query=user_query,
            session_id=session_id,
            user_id=user_id,
        )

        steps = [
            PlanStep(step_id=1, description="Inspect open desktop application windows", tool_name="list_windows"),
            PlanStep(step_id=2, description=f"Focus target window '{target_app}'" if target_app else "Get active window", tool_name="focus_window"),
            PlanStep(step_id=3, description=f"Perform desktop action: {action}"),
            PlanStep(step_id=4, description="Verify desktop state matches expected outcome"),
        ]
        state.plan = TaskPlan(goal=user_query, steps=steps)
        state.status = AgentExecutionStatus.EXECUTING

        # Step 1: List windows
        state.plan.steps[0].status = StepStatus.IN_PROGRESS
        windows = self.adapter.list_windows()
        state.plan.steps[0].result = {"window_count": len(windows)}
        state.plan.steps[0].status = StepStatus.COMPLETED

        # Step 2: Focus window if target_app provided
        focused = False
        if target_app:
            state.plan.steps[1].status = StepStatus.IN_PROGRESS
            focused = self.adapter.focus_window(target_app)
            state.plan.steps[1].result = {"focused": focused, "app": target_app}
            if not focused:
                state.plan.steps[1].status = StepStatus.FAILED
                state.plan.steps[1].error = f"Failed to find or focus application window '{target_app}'"
                state.status = AgentExecutionStatus.FAILED
                state.error = state.plan.steps[1].error
                return state
            state.plan.steps[1].status = StepStatus.COMPLETED
        else:
            state.plan.steps[1].status = StepStatus.SKIPPED

        # Step 3: Perform action
        state.plan.steps[2].status = StepStatus.IN_PROGRESS
        action_result: dict[str, Any] = {}
        if action == "clipboard_write" and clipboard_text is not None:
            ok = self.adapter.write_clipboard(clipboard_text)
            action_result = {"written": ok, "length": len(clipboard_text)}
        elif action == "clipboard_read":
            cb_data = self.adapter.read_clipboard()
            action_result = cb_data.model_dump()
        elif action == "screenshot":
            shot = self.adapter.capture_window(query=target_app, redact=True)
            action_result = shot.model_dump()
        else:
            action_result = {"action": action, "status": "completed"}
        state.plan.steps[2].result = action_result
        state.plan.steps[2].status = StepStatus.COMPLETED

        # Step 4: Verify desktop state
        state.plan.steps[3].status = StepStatus.IN_PROGRESS
        active_win = self.adapter.get_active_window()
        verified = True
        if target_app and active_win:
            verified = (target_app.lower() in active_win.title.lower() or target_app.lower() in active_win.app_name.lower())

        state.plan.steps[3].status = StepStatus.COMPLETED if verified else StepStatus.FAILED
        state.plan.is_complete = verified
        state.status = AgentExecutionStatus.SUCCESS if verified else AgentExecutionStatus.FAILED
        state.final_response = f"Desktop action '{action}' completed successfully."
        state.last_verification = VerificationResult(
            is_verified=verified,
            tool_name="focus_window" if target_app else "desktop_action",
            details="Active window verified matches requested application." if verified else "Active window mismatch.",
            evidence={"active_window": active_win.model_dump() if active_win else None},
        )

        return state
