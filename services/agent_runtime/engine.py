"""PIXEL Agent Runtime Engine.

High-level facade coordinating AgentGraph execution, tool registration,
checkpoint recovery, and user approval workflows.
"""

import logging

from packages.contracts.agent import (
    AgentExecutionStatus,
    AgentState,
)
from packages.contracts.intents import IntentPacket
from packages.core.interfaces.checkpointer import BaseCheckpointer
from packages.core.interfaces.os_adapter import BaseOSAdapter
from services.agent_runtime.checkpointing.sqlite_checkpointer import SQLiteCheckpointer
from services.agent_runtime.graph import AgentGraph
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.tools.builtin import (
    GetSystemInfoTool,
    LaunchAppTool,
    ListDirectoryTool,
    QueryMemoryTool,
    ReadFileTool,
    SearchKnowledgeTool,
    SetVolumeTool,
    WriteFileTool,
)
from services.agent_runtime.tools.registry import ToolRegistry
from services.memory.manager import MemoryManager
from services.os_control.mock_adapter import MockOSAdapter
from services.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


class AgentRuntimeEngine:
    """Unified engine for multi-step agent reasoning and execution."""

    def __init__(
        self,
        tool_registry: ToolRegistry | None = None,
        policy_gate: AgentPolicyGate | None = None,
        checkpointer: BaseCheckpointer | None = None,
        memory_manager: MemoryManager | None = None,
        rag_retriever: RAGRetriever | None = None,
        os_adapter: BaseOSAdapter | None = None,
    ) -> None:
        self.os_adapter = os_adapter or MockOSAdapter()
        self.tool_registry = tool_registry or self._create_default_registry(
            os_adapter=self.os_adapter,
            memory_manager=memory_manager,
            rag_retriever=rag_retriever,
        )
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.checkpointer = checkpointer or SQLiteCheckpointer()
        self.memory_manager = memory_manager
        self.rag_retriever = rag_retriever

        self.graph = AgentGraph(
            tool_registry=self.tool_registry,
            policy_gate=self.policy_gate,
            checkpointer=self.checkpointer,
            memory_manager=self.memory_manager,
            rag_retriever=self.rag_retriever,
        )

    def _create_default_registry(
        self,
        os_adapter: BaseOSAdapter,
        memory_manager: MemoryManager | None = None,
        rag_retriever: RAGRetriever | None = None,
    ) -> ToolRegistry:
        registry = ToolRegistry()
        # Filesystem
        registry.register_tool(ReadFileTool())
        registry.register_tool(WriteFileTool())
        registry.register_tool(ListDirectoryTool())
        # OS / System
        registry.register_tool(SetVolumeTool(os_adapter=os_adapter))
        registry.register_tool(LaunchAppTool(os_adapter=os_adapter))
        registry.register_tool(GetSystemInfoTool(os_adapter=os_adapter))
        # Memory & Knowledge
        if memory_manager:
            registry.register_tool(QueryMemoryTool(memory_manager=memory_manager))
        if rag_retriever:
            registry.register_tool(SearchKnowledgeTool(rag_retriever=rag_retriever))

        return registry

    async def execute_task(
        self,
        user_query: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
        intent_packet: IntentPacket | None = None,
    ) -> AgentState:
        """Executes a multi-step agent task."""
        state = AgentState(
            user_query=user_query,
            session_id=session_id,
            user_id=user_id,
            intent_packet=intent_packet,
        )
        return await self.graph.run(state)

    async def resume_approval(
        self,
        task_id: str,
        confirmation_token: str,
        user_approved: bool,
    ) -> AgentState | None:
        """Resumes execution of a paused task with user approval verdict."""
        return await self.graph.resume_with_approval(
            task_id=task_id,
            confirmation_token=confirmation_token,
            user_approved=user_approved,
        )

    async def get_state(self, task_id: str) -> AgentState | None:
        """Queries persisted state checkpoint."""
        return await self.checkpointer.get_latest_checkpoint(task_id)

    async def cancel_task(self, task_id: str) -> AgentState | None:
        """Cancels a pending or executing task."""
        state = await self.checkpointer.get_latest_checkpoint(task_id)
        if not state:
            return None

        state.status = AgentExecutionStatus.CANCELLED
        state.error = "Task cancelled by user request."
        await self.checkpointer.save_checkpoint(state)
        return state
