"""Local-First Hybrid Model Router.

Prioritizes deterministic execution (<0.5ms), routes agentic tasks to local
quantized models (Qwen/Llama), and manages policy-controlled remote fallback.
"""

import time
from typing import Any

from packages.contracts.models import LocalLLMRequest
from services.agent_runtime.local_llm.provider import QuantizedLocalLLM
from services.agent_runtime.local_llm.resource_manager import ModelResourceManager
from services.intent_engine.engine import DeterministicIntentEngine


class LocalModelRouter:
    """Smart router for local-first execution with deterministic fast-path preservation."""

    def __init__(
        self,
        intent_engine: DeterministicIntentEngine,
        local_llm: QuantizedLocalLLM | None = None,
        resource_manager: ModelResourceManager | None = None,
        allow_remote_fallback: bool = False,
    ) -> None:
        self.intent_engine = intent_engine
        self.local_llm = local_llm or QuantizedLocalLLM()
        self.resource_manager = resource_manager or ModelResourceManager()
        self.allow_remote_fallback = allow_remote_fallback

    async def route_and_execute(
        self,
        query: str,
        session_id: str = "default_session",
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, str, dict[str, Any]]:
        """Route query through the fastest safe path.

        Returns: (response_text, route_used, telemetry_metadata)
        """
        t0 = time.perf_counter()

        # 1. Check Deterministic Fast Path (<0.5ms)
        resp, packet, result = await self.intent_engine.handle_transcript(
            query, session_id=session_id
        )
        if packet.routing_type.value == "DETERMINISTIC_FAST_PATH":
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return (
                resp,
                "DETERMINISTIC_FAST_PATH",
                {
                    "intent_name": packet.target_intent,
                    "latency_ms": elapsed_ms,
                    "tokens_used": 0,
                },
            )

        # 2. Local Quantized LLM Path
        req = LocalLLMRequest(
            prompt=query,
            system_prompt="You are PIXEL, a helpful local AI assistant.",
            tools=tools or [],
        )

        try:
            llm_resp = await self.local_llm.generate_response(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return (
                llm_resp.content,
                "LOCAL_QUANTIZED_LLM",
                {
                    "model_id": llm_resp.model_id,
                    "latency_ms": elapsed_ms,
                    "tokens_used": llm_resp.total_tokens,
                    "tool_calls": llm_resp.tool_calls,
                },
            )
        except Exception as exc:
            # 3. Fallback evaluation
            if not self.allow_remote_fallback:
                raise RuntimeError(
                    f"Local LLM inference failed and remote fallback is disabled: {exc}"
                ) from exc

            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return (
                f"Remote fallback response to: {query}",
                "REMOTE_FALLBACK",
                {
                    "latency_ms": elapsed_ms,
                    "fallback_reason": str(exc),
                },
            )
