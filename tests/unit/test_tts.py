"""Unit tests for Text-to-Speech (TTS) Subsystem."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.contracts.errors import ModelException, ProviderUnavailableException
from services.voice_gateway.tts.edge_tts_provider import EdgeTTSProvider
from services.voice_gateway.tts.hybrid_tts import HybridTTSProvider
from services.voice_gateway.tts.kokoro_tts_provider import KokoroTTSProvider


class TestEdgeTTS:
    """Unit tests for Edge TTS provider."""

    def test_voice_resolution(self) -> None:
        tts = EdgeTTSProvider()
        assert tts._resolve_voice(None, "hi") == "hi-IN-SwaraNeural"
        assert tts._resolve_voice(None, "en") == "en-US-JennyNeural"
        assert tts._resolve_voice(None, "hinglish") == "hi-IN-MadhurNeural"
        assert tts._resolve_voice("custom-voice", "en") == "custom-voice"

    def test_missing_dependency_raises(self) -> None:
        tts = EdgeTTSProvider()
        with patch.dict("sys.modules", {"edge_tts": None}):
            # synthesize_stream will raise ProviderUnavailableException
            async def _run() -> None:
                async for _ in tts.synthesize_stream("hello"):
                    pass

            with pytest.raises(ProviderUnavailableException):
                import asyncio

                asyncio.run(_run())

    @pytest.mark.asyncio
    async def test_empty_text_returns_empty(self) -> None:
        tts = EdgeTTSProvider()
        res = await tts.synthesize_once("")
        assert res == b""

        stream_chunks = []
        async for chunk in tts.synthesize_stream("   "):
            stream_chunks.append(chunk)
        assert len(stream_chunks) == 0

    @pytest.mark.asyncio
    async def test_synthesize_stream_mocked(self) -> None:
        tts = EdgeTTSProvider()
        mock_communicate = MagicMock()

        async def _mock_stream() -> AsyncIterator[dict[str, object]]:
            yield {"type": "audio", "data": b"CHUNK1"}
            yield {"type": "Sentence", "data": "sentence metadata"}
            yield {"type": "audio", "data": b"CHUNK2"}

        mock_communicate.stream = _mock_stream
        mock_edge = MagicMock()
        mock_edge.Communicate.return_value = mock_communicate

        with patch.dict("sys.modules", {"edge_tts": mock_edge}):
            chunks = []
            async for chunk in tts.synthesize_stream("Namaste PIXEL", language="hi"):
                chunks.append(chunk)

            assert chunks == [b"CHUNK1", b"CHUNK2"]
            full_audio = await tts.synthesize_once("Namaste PIXEL", language="hi")
            assert full_audio == b"CHUNK1CHUNK2"


class TestKokoroTTS:
    """Unit tests for Kokoro local ONNX TTS provider."""

    def test_missing_model_raises_model_exception(self, tmp_path: object) -> None:
        import pathlib

        path = pathlib.Path(str(tmp_path)) / "nonexistent.onnx"
        tts = KokoroTTSProvider(model_path=str(path))
        with pytest.raises(ModelException):
            tts._ensure_loaded()

    @pytest.mark.asyncio
    async def test_synthesize_once_with_mock_session(self) -> None:
        tts = KokoroTTSProvider(model_path="dummy.onnx")
        tts._session = MagicMock()
        tts._is_loaded = True

        audio = await tts.synthesize_once("Test synthesis text")
        assert len(audio) > 0
        assert isinstance(audio, bytes)

    @pytest.mark.asyncio
    async def test_synthesize_stream_chunks(self) -> None:
        tts = KokoroTTSProvider(model_path="dummy.onnx")
        tts._session = MagicMock()
        tts._is_loaded = True

        chunks = []
        async for chunk in tts.synthesize_stream("Streaming audio generation"):
            chunks.append(chunk)

        assert len(chunks) >= 1
        assert b"".join(chunks) == await tts.synthesize_once("Streaming audio generation")


class TestHybridTTS:
    """Unit tests for Hybrid TTS provider."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        primary = EdgeTTSProvider()
        primary.synthesize_once = AsyncMock(side_effect=RuntimeError("EdgeTTS network down"))  # type: ignore

        fallback = KokoroTTSProvider(model_path="dummy.onnx")
        fallback.synthesize_once = AsyncMock(return_value=b"FALLBACK_PCM_AUDIO")  # type: ignore

        hybrid = HybridTTSProvider(primary_provider=primary, fallback_provider=fallback)
        audio = await hybrid.synthesize_once("Testing fallback")

        assert audio == b"FALLBACK_PCM_AUDIO"
        fallback.synthesize_once.assert_called_once()
