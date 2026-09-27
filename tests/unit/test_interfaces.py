"""Unit tests verifying abstract core interfaces with mock implementations."""

from collections.abc import AsyncIterator
from typing import Any

import pytest

from packages.contracts.events import AudioFrame, TranscriptEvent
from packages.contracts.memory import FactRecord
from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces import (
    BaseMemoryStore,
    BaseSTTProvider,
    BaseTool,
    BaseTTSProvider,
)


class MockSTT(BaseSTTProvider):
    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        session_id: str,
        language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        async for _ in audio_stream:
            yield TranscriptEvent(session_id=session_id, text="hello", is_final=True)

    async def transcribe_once(
        self,
        audio_bytes: bytes,
        language: str | None = None
    ) -> TranscriptEvent:
        return TranscriptEvent(session_id="mock", text="test audio", is_final=True)


class MockTTS(BaseTTSProvider):
    async def synthesize_stream(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn"
    ) -> AsyncIterator[bytes]:
        yield b"chunk1"
        yield b"chunk2"

    async def synthesize_once(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn"
    ) -> bytes:
        return b"complete_audio"


class MockTool(BaseTool):
    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="mock_tool",
            description="Mock capability",
            risk_class=RiskClass.READ,
            parameters_schema={},
            audit_level=AuditLevel.BASIC
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        return ToolExecutionResult(success=True, output="mock_done")


class MockMemory(BaseMemoryStore):
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    async def get_fact(self, key: str, user_id: str) -> Any | None:
        return self._store.get(f"{user_id}:{key}")

    async def set_fact(
        self,
        key: str,
        value: Any,
        user_id: str,
        category: str = "general",
        provenance: str = "user_explicit",
        confidence: float = 1.0,
    ) -> FactRecord:
        self._store[f"{user_id}:{key}"] = value
        return FactRecord(
            fact_id="mock_fact",
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            provenance=provenance,
            is_active=True,
        )

    async def delete_fact(self, key: str, user_id: str) -> bool:
        k = f"{user_id}:{key}"
        if k in self._store:
            del self._store[k]
            return True
        return False

    async def search_episodic(self, query: str, user_id: str, limit: int = 5) -> list[dict[str, Any]]:
        return [{"query": query, "match": "mock_episode"}]


@pytest.mark.asyncio
async def test_mock_stt_transcribe_once() -> None:
    stt = MockSTT()
    res = await stt.transcribe_once(b"1234")
    assert res.text == "test audio"
    assert res.is_final is True


@pytest.mark.asyncio
async def test_mock_tts_synthesize() -> None:
    tts = MockTTS()
    audio = await tts.synthesize_once("Namaste")
    assert audio == b"complete_audio"


@pytest.mark.asyncio
async def test_mock_tool_execution() -> None:
    tool = MockTool()
    assert tool.spec.name == "mock_tool"
    res = await tool.execute({}, session_id="s1")
    assert res.success is True
    assert res.output == "mock_done"


@pytest.mark.asyncio
async def test_mock_memory_store() -> None:
    mem = MockMemory()
    await mem.set_fact("preferred_name", "Vaibhav", user_id="u1")
    val = await mem.get_fact("preferred_name", user_id="u1")
    assert val == "Vaibhav"

    deleted = await mem.delete_fact("preferred_name", user_id="u1")
    assert deleted is True
    assert await mem.get_fact("preferred_name", user_id="u1") is None
