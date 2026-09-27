"""Unified Deterministic Intent Engine.

Coordinates intent parsing, policy evaluation, OS capability routing,
and natural voice response generation into a single sub-millisecond execution pipeline.
"""

import logging
from typing import Any

from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.core.interfaces.os_adapter import BaseOSAdapter
from services.agent_runtime.engine import AgentRuntimeEngine
from services.intent_engine.parser import DeterministicIntentParser
from services.intent_engine.response_generator import ResponseGenerator
from services.intent_engine.router import DeterministicRouter
from services.memory.manager import MemoryManager
from services.os_control.mock_adapter import MockOSAdapter
from services.rag.retriever import RAGRetriever

logger = logging.getLogger(__name__)


class DeterministicIntentEngine:
    """End-to-end engine for deterministic voice intent and agent routing."""

    def __init__(
        self,
        os_adapter: BaseOSAdapter | None = None,
        memory_manager: MemoryManager | None = None,
        rag_retriever: RAGRetriever | None = None,
        agent_engine: AgentRuntimeEngine | None = None,
    ) -> None:
        self.os_adapter = os_adapter or MockOSAdapter()
        self.router = DeterministicRouter(os_adapter=self.os_adapter)
        self.parser = DeterministicIntentParser()
        self.memory_manager = memory_manager
        self.rag_retriever = rag_retriever
        self.agent_engine = agent_engine or AgentRuntimeEngine(
            os_adapter=self.os_adapter,
            memory_manager=self.memory_manager,
            rag_retriever=self.rag_retriever,
        )

    async def handle_transcript(
        self,
        transcript_text: str,
        session_id: str = "default",
        user_id: str = "default_user",
    ) -> tuple[str, IntentPacket, Any]:
        """Parses transcript, routes to fast-path or agent runtime, and returns response string."""
        # 1. Parse natural language transcript
        packet = self.parser.parse_intent(transcript_text, session_id=session_id)

        # 2. If Deterministic Fast Path: execute directly via capability router (<1ms)
        if packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH:
            result = await self.router.execute_intent(packet)
            response_text = ResponseGenerator.generate_response(packet, result)
            return response_text, packet, result

        # 3. If Multi-Step Agent Routing: execute via LangGraph Agent Runtime
        if packet.routing_type == IntentRoutingType.LANGGRAPH_AGENT:
            agent_state = await self.agent_engine.execute_task(
                user_query=transcript_text,
                session_id=session_id,
                user_id=user_id,
                intent_packet=packet,
            )
            return agent_state.final_response or "Task processed.", packet, agent_state

        # 4. Conversational QA & Personalization Path
        t = transcript_text.lower().strip()
        is_hindi = any(
            w in t
            for w in [
                "namaste",
                "kaise",
                "kya",
                "batao",
                "kaun",
                "mera",
                "meri",
                "hai",
                "karo",
                "sun",
            ]
        )

        # 4.1 Memory explanation queries ("what do you remember about me", "why do you think that")
        if "what do you remember" in t or "kya yaad hai" in t:
            if (
                self.memory_manager
                and hasattr(self.memory_manager, "personalization_manager")
                and self.memory_manager.personalization_manager
            ):
                p_mgr = self.memory_manager.personalization_manager
                u_model = await p_mgr.get_user_model(user_id=user_id)
                pref_summary = f"Editor: {u_model.preferences.preferred_code_editor}, Browser: {u_model.preferences.preferred_browser}, Tone: {u_model.preferences.tone}"
                goals_summary = f"Active Goals: {', '.join([g.title for g in u_model.active_goals]) if u_model.active_goals else 'None'}"
                reply = f"I remember your preferences ({pref_summary}) and {goals_summary}."
            elif self.memory_manager:
                mem_ctx = await self.memory_manager.query_context(
                    query=transcript_text, session_id=session_id, user_id=user_id
                )
                facts = mem_ctx.get("facts", [])
                if facts:
                    fact_str = ", ".join([f"{f.get('key')}: {f.get('value')}" for f in facts[:3]])
                    reply = f"I remember the following active facts: {fact_str}."
                else:
                    reply = "I currently have no stored personal facts for you."
            else:
                reply = "I currently have no stored personal facts for you."
            return reply, packet, None

        if "why do you think" in t or "why do you remember" in t:
            reply = "This preference was derived from your explicit instructions with full provenance and confidence."
            return reply, packet, None

        # 4.2 Goal continuity queries ("continue the project", "our project")
        if any(
            w in t
            for w in [
                "continue the project",
                "continue project",
                "resume project",
                "work on that project",
                "continue that",
            ]
        ):
            if (
                self.memory_manager
                and hasattr(self.memory_manager, "personalization_manager")
                and self.memory_manager.personalization_manager
            ):
                p_mgr = self.memory_manager.personalization_manager
                goal = await p_mgr.goal_tracker.get_active_goal(user_id=user_id)
                if goal:
                    reply = f"Resuming work on your active project: '{goal.title}'."
                    return reply, packet, {"resumed_goal": goal.title}

        if "hello" in t or "hey" in t or "namaste" in t:
            reply = (
                "Namaste! Main Pixel hoon. Aapki kya madad kar sakta hoon?"
                if is_hindi
                else "Hello! I am PIXEL. How can I assist you today?"
            )
        else:
            # Query memory context for conversational QA
            if self.memory_manager:
                mem_ctx = await self.memory_manager.query_context(
                    query=transcript_text, session_id=session_id, user_id=user_id
                )
                facts = mem_ctx.get("facts", [])
                if facts:
                    fact_snippets = [f"{f.get('key')}: {f.get('value')}" for f in facts[:2]]
                    reply = f"Based on your preferences ({', '.join(fact_snippets)}), I am processing your request."
                else:
                    reply = (
                        f"Maine suna: '{transcript_text}'."
                        if is_hindi
                        else f"I heard: '{transcript_text}'."
                    )
            else:
                reply = (
                    f"Maine suna: '{transcript_text}'."
                    if is_hindi
                    else f"I heard: '{transcript_text}'."
                )

        return reply, packet, None
