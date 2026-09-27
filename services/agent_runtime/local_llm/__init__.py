"""Quantized Local LLM Engine & Model Resource Manager.

Provides 4-bit quantized local neural model inference, model lifecycle management,
hardware resource tracking, and local-first intent routing.
"""

from services.agent_runtime.local_llm.provider import QuantizedLocalLLM
from services.agent_runtime.local_llm.resource_manager import ModelResourceManager
from services.agent_runtime.local_llm.router import LocalModelRouter

__all__ = [
    "QuantizedLocalLLM",
    "ModelResourceManager",
    "LocalModelRouter",
]
