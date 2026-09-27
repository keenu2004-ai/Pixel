"""Agent Planner and Internal Critic Module.

Formulates structured execution plans, resolves step dependencies,
and evaluates execution outcomes to detect completion or needed replanning.
"""

import logging
from typing import Any

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
    PlanStep,
    StepStatus,
    TaskPlan,
)
from packages.contracts.tools import ToolSpec

logger = logging.getLogger(__name__)


class AgentPlanner:
    """Deterministic and heuristic planning engine for multi-step agent tasks."""

    @classmethod
    def formulate_plan(
        cls,
        user_query: str,
        available_tools: list[ToolSpec],
        rag_context: str | None = None,
        semantic_facts: list[dict[str, Any]] | None = None,
    ) -> TaskPlan:
        """Formulates an initial structured plan for a user query."""
        tool_names = {t.name for t in available_tools}
        q_lower = user_query.lower()
        steps: list[PlanStep] = []

        # 1. Multi-step Research & Save Pattern (e.g., "Find information about X, and save to notes.txt")
        if (
            "search" in q_lower or "find" in q_lower or "read" in q_lower or "check" in q_lower
        ) and ("save" in q_lower or "write" in q_lower or "create file" in q_lower):
            if "search_knowledge" in tool_names and "write_file" in tool_names:
                steps.append(
                    PlanStep(
                        step_id=1,
                        description="Retrieve relevant knowledge from documentation or code",
                        tool_name="search_knowledge",
                        arguments={"query": user_query, "top_k": 3},
                    )
                )
                # Extract target path if specified
                target_file = "notes.txt"
                if "to " in q_lower:
                    parts = q_lower.split("to ")
                    if len(parts) > 1:
                        target_file = parts[1].split()[0].strip()

                steps.append(
                    PlanStep(
                        step_id=2,
                        description=f"Save retrieved information to {target_file}",
                        tool_name="write_file",
                        arguments={"path": target_file, "content": "Knowledge Summary Placeholder"},
                        dependencies=[1],
                    )
                )

        # 2. Direct File Read Pattern
        elif ("read" in q_lower or "show" in q_lower or "open" in q_lower) and (
            "file" in q_lower or ".txt" in q_lower or ".md" in q_lower or ".py" in q_lower
        ):
            if "read_file" in tool_names:
                # Extract file path token
                words = user_query.split()
                file_candidate = "output.txt"
                for w in words:
                    if "." in w and not w.endswith("."):
                        file_candidate = w.strip("'\"")
                        break
                steps.append(
                    PlanStep(
                        step_id=1,
                        description=f"Read file '{file_candidate}'",
                        tool_name="read_file",
                        arguments={"path": file_candidate},
                    )
                )

        # 3. Direct File Write Pattern
        elif "write" in q_lower or "save" in q_lower or "create file" in q_lower:
            if "write_file" in tool_names:
                words = user_query.split()
                file_candidate = "output.txt"
                for w in words:
                    if "." in w and not w.endswith("."):
                        file_candidate = w.strip("'\"")
                        break
                steps.append(
                    PlanStep(
                        step_id=1,
                        description=f"Write content to '{file_candidate}'",
                        tool_name="write_file",
                        arguments={
                            "path": file_candidate,
                            "content": f"Generated for: {user_query}",
                        },
                    )
                )

        # 4. System Telemetry / Info Pattern
        elif "battery" in q_lower or "system info" in q_lower or "power" in q_lower:
            if "get_system_info" in tool_names:
                steps.append(
                    PlanStep(
                        step_id=1,
                        description="Query OS and battery status",
                        tool_name="get_system_info",
                        arguments={},
                    )
                )

        # 5. Direct Tool Name / Capability Matching
        if not steps:
            for spec in available_tools:
                tool_tokens = spec.name.lower().split("_")
                if all(tok in q_lower for tok in tool_tokens) or spec.name.lower() in q_lower:
                    # Extract arguments from query if possible
                    args: dict[str, Any] = {}
                    if "drive" in spec.parameters_schema.get("properties", {}):
                        words = user_query.split()
                        for w in words:
                            if ":" in w:
                                args["drive"] = w
                    steps.append(
                        PlanStep(
                            step_id=1,
                            description=f"Execute {spec.name}",
                            tool_name=spec.name,
                            arguments=args,
                        )
                    )
                    break

        # 6. Fallback Knowledge Search
        if not steps and "search_knowledge" in tool_names:
            steps.append(
                PlanStep(
                    step_id=1,
                    description="Retrieve technical knowledge context",
                    tool_name="search_knowledge",
                    arguments={"query": user_query, "top_k": 3},
                )
            )

        # 7. If no tools matched, single direct completion step
        if not steps:
            steps.append(
                PlanStep(
                    step_id=1,
                    description=f"Execute task: {user_query}",
                    tool_name=None,
                    arguments={},
                )
            )

        return TaskPlan(goal=user_query, steps=steps, current_step_index=0, is_complete=False)

    @classmethod
    def evaluate_step_outcome(
        cls,
        state: AgentState,
    ) -> tuple[AgentExecutionStatus, str | None]:
        """Evaluates latest step outcome and decides whether to continue, retry, replan, or finish."""
        if not state.plan:
            return AgentExecutionStatus.SUCCESS, "Task completed."

        current_idx = state.plan.current_step_index
        if current_idx >= len(state.plan.steps):
            state.plan.is_complete = True
            return AgentExecutionStatus.SUCCESS, "All planned steps completed."

        current_step = state.plan.steps[current_idx]

        # If last execution failed
        if state.last_tool_result and not state.last_tool_result.success:
            current_step.status = StepStatus.FAILED
            current_step.error = state.last_tool_result.error

            # Transient failure retry check
            if state.retry_count < state.max_retries:
                state.retry_count += 1
                logger.info(
                    "Retrying step %d (attempt %d/%d)",
                    current_step.step_id,
                    state.retry_count,
                    state.max_retries,
                )
                current_step.status = StepStatus.IN_PROGRESS
                return AgentExecutionStatus.EXECUTING, f"Retrying step {current_step.step_id}"

            return (
                AgentExecutionStatus.FAILED,
                f"Step {current_step.step_id} failed: {state.last_tool_result.error}",
            )

        # If last execution succeeded and verified
        if state.last_tool_result and state.last_tool_result.success:
            current_step.status = StepStatus.COMPLETED
            current_step.result = state.last_tool_result.output

            # If this was a search step feeding into a write step, propagate evidence
            if current_step.tool_name == "search_knowledge" and current_idx + 1 < len(
                state.plan.steps
            ):
                next_step = state.plan.steps[current_idx + 1]
                if next_step.tool_name == "write_file":
                    # Update content argument with the retrieved knowledge
                    retrieved_text = (
                        str(current_step.result.get("formatted_context", ""))
                        if isinstance(current_step.result, dict)
                        else str(current_step.result)
                    )
                    next_step.arguments["content"] = retrieved_text

            # Advance to next step
            state.plan.current_step_index += 1
            if state.plan.current_step_index >= len(state.plan.steps):
                state.plan.is_complete = True
                return AgentExecutionStatus.SUCCESS, "All planned steps completed."

            return (
                AgentExecutionStatus.PLANNING,
                f"Proceeding to step {state.plan.current_step_index + 1}",
            )

        return AgentExecutionStatus.EXECUTING, None
