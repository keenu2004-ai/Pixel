"""Stateful Agent Execution Graph & Runtime Coordinator.

Implements the multi-step state graph with bounded execution,
L6 policy approval gates, L8 verification, and state checkpointing.
"""

import logging
from datetime import UTC, datetime

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
    StepStatus,
)
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import ToolExecutionRequest
from packages.core.interfaces.checkpointer import BaseCheckpointer
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer
from services.agent_runtime.planner import AgentPlanner
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.registry import ToolRegistry
from services.agent_runtime.verifier import ActionVerifier
from services.memory.manager import MemoryManager
from services.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


class AgentGraph:
    """Stateful LangGraph-equivalent agent execution engine for PIXEL."""

    def __init__(
        self,
        tool_registry: ToolRegistry,
        policy_gate: AgentPolicyGate | None = None,
        checkpointer: BaseCheckpointer | None = None,
        memory_manager: MemoryManager | None = None,
        rag_retriever: RAGRetriever | None = None,
    ) -> None:
        self.tool_registry = tool_registry
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.checkpointer = checkpointer or SQLiteCheckpointer()
        self.memory_manager = memory_manager
        self.rag_retriever = rag_retriever

    # -----------------------------------------------------------------------
    # Graph Nodes
    # -----------------------------------------------------------------------

    async def node_context_enrichment(self, state: AgentState) -> AgentState:
        """Enriches initial state with Working Memory, Facts, and RAG knowledge."""
        logger.debug("Executing node_context_enrichment for task %s", state.task_id)

        # 1. Fetch Working Memory & Semantic Facts
        if self.memory_manager:
            try:
                mem_ctx = await self.memory_manager.query_context(
                    query=state.user_query,
                    session_id=state.session_id,
                    user_id=state.user_id,
                )
                state.working_memory = mem_ctx.get("working_context", [])
                state.semantic_facts = mem_ctx.get("facts", [])
            except Exception as err:
                logger.warning("Memory context retrieval failed: %s", err)

        # 2. Retrieve RAG Evidence (if query requires technical/doc knowledge)
        if self.rag_retriever:
            try:
                rag_ctx = await self.rag_retriever.retrieve_and_assemble(
                    query=state.user_query,
                    max_tokens=600,
                )
                state.rag_context = rag_ctx
            except Exception as err:
                logger.warning("RAG retrieval failed: %s", err)

        state.updated_at = datetime.now(UTC)
        return state

    async def node_planner(self, state: AgentState) -> AgentState:
        """Formulates bounded execution plan."""
        logger.debug("Executing node_planner for task %s", state.task_id)
        available_specs = self.tool_registry.list_specs()
        rag_text = state.rag_context.formatted_context if state.rag_context else None

        state.plan = AgentPlanner.formulate_plan(
            user_query=state.user_query,
            available_tools=available_specs,
            rag_context=rag_text,
            semantic_facts=state.semantic_facts,
        )
        state.status = AgentExecutionStatus.PLANNING
        state.updated_at = datetime.now(UTC)
        return state

    async def node_tool_selector(self, state: AgentState) -> AgentState:
        """Selects next tool from the active plan step."""
        logger.debug("Executing node_tool_selector for task %s", state.task_id)
        if not state.plan or state.plan.is_complete:
            state.pending_tool_name = None
            state.pending_tool_arguments = {}
            return state

        current_idx = state.plan.current_step_index
        if current_idx < len(state.plan.steps):
            step = state.plan.steps[current_idx]
            state.pending_tool_name = step.tool_name
            state.pending_tool_arguments = step.arguments
            step.status = StepStatus.IN_PROGRESS
        else:
            state.pending_tool_name = None
            state.pending_tool_arguments = {}

        state.status = AgentExecutionStatus.EXECUTING
        state.updated_at = datetime.now(UTC)
        return state

    async def node_policy_gate(
        self,
        state: AgentState,
        confirmation_token: str | None = None,
        is_user_confirmed: bool = False,
    ) -> AgentState:
        """Evaluates pending tool request against L6 Policy Engine."""
        logger.debug("Executing node_policy_gate for task %s", state.task_id)
        if not state.pending_tool_name:
            return state

        tool_spec = self.tool_registry.get_tool_spec(state.pending_tool_name)
        if not tool_spec:
            state.status = AgentExecutionStatus.FAILED
            state.error = f"Tool '{state.pending_tool_name}' not found in registry"
            return state

        decision, approval_card = self.policy_gate.evaluate(
            tool_spec=tool_spec,
            arguments=state.pending_tool_arguments,
            task_id=state.task_id,
            session_id=state.session_id,
            user_id=state.user_id,
            confirmation_token=confirmation_token,
            is_user_confirmed=is_user_confirmed,
        )

        state.last_policy_decision = decision
        state.pending_approval = approval_card

        if decision.verdict == PolicyVerdict.DENY:
            state.status = AgentExecutionStatus.POLICY_DENIED
            state.error = f"Policy Denied: {decision.reason}"
            logger.warning("Task %s blocked by Policy: %s", state.task_id, decision.reason)
        elif decision.verdict == PolicyVerdict.REQUIRE_USER_CONFIRMATION:
            state.status = AgentExecutionStatus.AWAITING_APPROVAL
            logger.info("Task %s paused awaiting user approval for tool '%s'", state.task_id, state.pending_tool_name)
        else:
            state.status = AgentExecutionStatus.EXECUTING

        state.updated_at = datetime.now(UTC)
        return state

    async def node_executor(self, state: AgentState) -> AgentState:
        """Executes tool through ToolRegistry and records audit log."""
        logger.debug("Executing node_executor for task %s", state.task_id)
        if not state.pending_tool_name or state.status != AgentExecutionStatus.EXECUTING:
            return state

        req = ToolExecutionRequest(
            tool_name=state.pending_tool_name,
            arguments=state.pending_tool_arguments,
            session_id=state.session_id,
            trace_id=state.trace_id,
            caller_agent_id="langgraph_agent_runtime",
        )

        result = await self.tool_registry.execute_tool(req)
        state.last_tool_result = result

        # Record audit
        tool_spec = self.tool_registry.get_tool_spec(state.pending_tool_name)
        if tool_spec and state.last_policy_decision:
            self.policy_gate.record_audit(
                actor_id=state.user_id,
                tool_spec=tool_spec,
                arguments=state.pending_tool_arguments,
                decision=state.last_policy_decision,
                trace_id=state.trace_id,
                execution_success=result.success,
            )

        # Record into tool history
        state.tool_history.append({
            "step": state.current_step,
            "tool": state.pending_tool_name,
            "arguments": state.pending_tool_arguments,
            "success": result.success,
            "output": result.output,
            "error": result.error,
        })

        state.status = AgentExecutionStatus.VERIFYING
        state.updated_at = datetime.now(UTC)
        return state

    async def node_verifier(self, state: AgentState) -> AgentState:
        """Performs L8 verification on the executed action."""
        logger.debug("Executing node_verifier for task %s", state.task_id)
        if not state.pending_tool_name or not state.last_tool_result:
            return state

        verification = await ActionVerifier.verify(
            tool_name=state.pending_tool_name,
            arguments=state.pending_tool_arguments,
            result=state.last_tool_result,
        )
        state.last_verification = verification
        state.updated_at = datetime.now(UTC)
        return state

    async def node_critic_replan(self, state: AgentState) -> AgentState:
        """Evaluates step progress, checks hard bounds, and determines next transition."""
        logger.debug("Executing node_critic_replan for task %s", state.task_id)
        state.current_step += 1

        # Check hard step bound
        if state.current_step >= state.max_steps:
            state.status = AgentExecutionStatus.MAX_STEPS_EXCEEDED
            state.error = f"Hard execution bound reached: {state.max_steps} steps exceeded."
            logger.warning("Task %s halted: max steps exceeded", state.task_id)
            return state

        next_status, reason = AgentPlanner.evaluate_step_outcome(state)
        state.status = next_status
        if next_status == AgentExecutionStatus.FAILED:
            state.error = reason

        state.updated_at = datetime.now(UTC)
        return state

    async def node_final_response(self, state: AgentState) -> AgentState:
        """Generates clear, concise final user response."""
        logger.debug("Executing node_final_response for task %s", state.task_id)
        if state.status == AgentExecutionStatus.SUCCESS:
            outputs: list[str] = []
            if state.plan:
                for s in state.plan.steps:
                    if s.status == StepStatus.COMPLETED:
                        outputs.append(f"✓ {s.description}")
            summary = "\n".join(outputs) if outputs else "Task completed successfully."
            state.final_response = f"Done! {summary}"
        elif state.status == AgentExecutionStatus.AWAITING_APPROVAL:
            state.final_response = f"Action requires your approval: {state.pending_approval.reason if state.pending_approval else 'Confirmation needed'}"
        elif state.status == AgentExecutionStatus.POLICY_DENIED:
            state.final_response = f"Action blocked by policy: {state.error}"
        elif state.status == AgentExecutionStatus.FAILED:
            state.final_response = f"I encountered an issue completing this task: {state.error}"
        elif state.status == AgentExecutionStatus.MAX_STEPS_EXCEEDED:
            state.final_response = f"Task aborted: Maximum step limit reached ({state.max_steps} steps)."
        else:
            state.final_response = f"Task finished with status: {state.status.value}"

        state.updated_at = datetime.now(UTC)
        return state

    # -----------------------------------------------------------------------
    # Main Execution Loop
    # -----------------------------------------------------------------------

    async def run(self, state: AgentState) -> AgentState:
        """Executes the agent graph loop until termination or pause."""
        # 1. Context Enrichment
        state = await self.node_context_enrichment(state)

        # 2. Plan formulation
        state = await self.node_planner(state)
        await self.checkpointer.save_checkpoint(state)

        # 3. Main Loop
        while state.status in (AgentExecutionStatus.PLANNING, AgentExecutionStatus.EXECUTING, AgentExecutionStatus.VERIFYING):
            # Select Tool
            state = await self.node_tool_selector(state)
            if not state.pending_tool_name:
                state.status = AgentExecutionStatus.SUCCESS
                break

            # Policy Gate
            state = await self.node_policy_gate(state)

            # If awaiting approval or policy denied -> break loop & save checkpoint
            if state.status in (AgentExecutionStatus.AWAITING_APPROVAL, AgentExecutionStatus.POLICY_DENIED, AgentExecutionStatus.FAILED):
                await self.checkpointer.save_checkpoint(state)
                break

            # Execute Tool
            state = await self.node_executor(state)

            # Verify
            state = await self.node_verifier(state)

            # Critic & Replan
            state = await self.node_critic_replan(state)
            await self.checkpointer.save_checkpoint(state)

        # 4. Generate Final Response
        state = await self.node_final_response(state)
        await self.checkpointer.save_checkpoint(state)

        # 5. Record interaction in working memory if memory manager configured
        if self.memory_manager and state.final_response:
            await self.memory_manager.record_interaction(
                user_input=state.user_query,
                agent_response=state.final_response,
                session_id=state.session_id,
                user_id=state.user_id,
            )

        return state

    async def resume_with_approval(
        self,
        task_id: str,
        confirmation_token: str,
        user_approved: bool,
    ) -> AgentState | None:
        """Resumes a paused task following user confirmation decision."""
        state = await self.checkpointer.get_latest_checkpoint(task_id)
        if not state:
            logger.error("No checkpoint found to resume task %s", task_id)
            return None

        if state.status != AgentExecutionStatus.AWAITING_APPROVAL:
            logger.warning("Task %s is not in AWAITING_APPROVAL state (current: %s)", task_id, state.status)
            return state

        if not user_approved:
            state.status = AgentExecutionStatus.POLICY_DENIED
            state.error = "User rejected tool approval request"
            if state.pending_approval:
                state.pending_approval.is_resolved = True
                state.pending_approval.user_approved = False
            state = await self.node_final_response(state)
            await self.checkpointer.save_checkpoint(state)
            return state

        # Resolve approval card
        if state.pending_approval:
            state.pending_approval.is_resolved = True
            state.pending_approval.user_approved = True

        # Re-evaluate policy gate with user confirmation token
        state = await self.node_policy_gate(
            state,
            confirmation_token=confirmation_token,
            is_user_confirmed=True,
        )

        if state.status == AgentExecutionStatus.POLICY_DENIED:
            state = await self.node_final_response(state)
            await self.checkpointer.save_checkpoint(state)
            return state

        # Continue loop execution
        return await self.run_from_step(state)

    async def run_from_step(self, state: AgentState) -> AgentState:
        """Resumes main loop execution from active tool step."""
        while state.status in (AgentExecutionStatus.PLANNING, AgentExecutionStatus.EXECUTING, AgentExecutionStatus.VERIFYING):
            if state.status == AgentExecutionStatus.EXECUTING and state.pending_tool_name:
                state = await self.node_executor(state)
                state = await self.node_verifier(state)
                state = await self.node_critic_replan(state)
                await self.checkpointer.save_checkpoint(state)
                continue

            state = await self.node_tool_selector(state)
            if not state.pending_tool_name:
                state.status = AgentExecutionStatus.SUCCESS
                break

            state = await self.node_policy_gate(state)
            if state.status in (AgentExecutionStatus.AWAITING_APPROVAL, AgentExecutionStatus.POLICY_DENIED, AgentExecutionStatus.FAILED):
                await self.checkpointer.save_checkpoint(state)
                break

            state = await self.node_executor(state)
            state = await self.node_verifier(state)
            state = await self.node_critic_replan(state)
            await self.checkpointer.save_checkpoint(state)

        state = await self.node_final_response(state)
        await self.checkpointer.save_checkpoint(state)

        if self.memory_manager and state.final_response:
            await self.memory_manager.record_interaction(
                user_input=state.user_query,
                agent_response=state.final_response,
                session_id=state.session_id,
                user_id=state.user_id,
            )

        return state
