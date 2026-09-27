"""Unified Deterministic Intent Engine.

Coordinates intent parsing, policy evaluation, OS capability routing,
and natural voice response generation into a single sub-millisecond execution pipeline.
"""

import logging
from typing import Any

from packages.contracts.intents import IntentPacket, IntentRoutingType
from packages.core.interfaces.os_adapter import BaseOSAdapter
from services.intent_engine.parser import DeterministicIntentParser
from services.intent_engine.response_generator import ResponseGenerator
from services.intent_engine.router import DeterministicRouter
from services.os_control.mock_adapter import MockOSAdapter

logger = logging.getLogger(__name__)


class DeterministicIntentEngine:
    """End-to-end engine for deterministic voice intent handling."""

    def __init__(self, os_adapter: BaseOSAdapter | None = None) -> None:
        self.os_adapter = os_adapter or MockOSAdapter()
        self.router = DeterministicRouter(os_adapter=self.os_adapter)
        self.parser = DeterministicIntentParser()

    async def handle_transcript(
        self,
        transcript_text: str,
        session_id: str = "default",
    ) -> tuple[str, IntentPacket, Any]:
        """Parses transcript, executes deterministic tool, and returns response string."""
        # 1. Parse natural language transcript
        packet = self.parser.parse_intent(transcript_text, session_id=session_id)

        # 2. If Deterministic Fast Path: execute via capability router
        if packet.routing_type == IntentRoutingType.DETERMINISTIC_FAST_PATH:
            result = await self.router.execute_intent(packet)
            response_text = ResponseGenerator.generate_response(packet, result)
            return response_text, packet, result

        # 3. Conversational QA Fallback (until Phase 4 LLM agent)
        t = transcript_text.lower().strip()
        is_hindi = any(w in t for w in ["namaste", "kaise", "kya", "batao", "kaun"])
        if "hello" in t or "hey" in t or "namaste" in t:
            reply = "Namaste! Main Pixel hoon. Aapki kya madad kar sakta hoon?" if is_hindi else "Hello! I am PIXEL. How can I assist you today?"
        else:
            reply = f"Maine suna: '{transcript_text}'. Agle phase me main iska conversational uttar dunga." if is_hindi else f"I heard: '{transcript_text}'. Full conversational reasoning will be enabled in Phase 4."

        return reply, packet, None
