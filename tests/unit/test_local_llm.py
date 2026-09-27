"""Unit tests for QuantizedLocalLLM and local inference."""

import pytest

from packages.contracts.models import (
    LocalLLMRequest,
    ModelFamily,
    ModelLifecycleState,
    ModelMetadata,
    QuantizationType,
)
from services.agent_runtime.local_llm.provider import QuantizedLocalLLM


def test_model_lifecycle_states() -> None:
    llm = QuantizedLocalLLM()
    assert llm.get_state() == ModelLifecycleState.UNLOADED

    assert llm.load_model() is True
    assert llm.get_state() == ModelLifecycleState.READY

    assert llm.unload_model() is True
    assert llm.get_state() == ModelLifecycleState.UNLOADED


@pytest.mark.asyncio
async def test_local_llm_inference_and_tool_call() -> None:
    meta = ModelMetadata(
        model_id="qwen2.5-coder-7b-q4",
        model_name="Qwen 2.5 Coder 7B",
        family=ModelFamily.QWEN,
        quantization=QuantizationType.Q4_K_M,
        file_path="data/models/llm/qwen.gguf",
        sha256_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    )
    llm = QuantizedLocalLLM(metadata=meta)

    # Request requiring file tool
    req = LocalLLMRequest(
        prompt="Please read file main.py",
        tools=[{"name": "read_file", "description": "Read file contents"}],
    )
    resp = await llm.generate_response(req)
    assert resp.model_id == "qwen2.5-coder-7b-q4"
    assert resp.quantization == QuantizationType.Q4_K_M
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0]["name"] == "read_file"
    assert resp.total_tokens > 0


@pytest.mark.asyncio
async def test_local_llm_streaming() -> None:
    llm = QuantizedLocalLLM()
    req = LocalLLMRequest(prompt="Summarize the system status")

    streamed_tokens: list[str] = []
    async for token in llm.generate_response_stream(req):
        streamed_tokens.append(token)

    assert len(streamed_tokens) > 0
    full_text = "".join(streamed_tokens)
    assert len(full_text.strip()) > 0
