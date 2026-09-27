"""Unit tests for Speech-to-Text (STT) Subsystem."""

from collections.abc import AsyncIterator
from unittest.mock import MagicMock, patch

import pytest

from packages.contracts.errors import ProviderUnavailableException
from packages.contracts.events import AudioFrame
from services.voice_gateway.stt.cloud_stt_provider import CloudSTTProvider
from services.voice_gateway.stt.hybrid_stt import HybridSTTProvider
from services.voice_gateway.stt.whisper_provider import LocalWhisperSTT


class TestLocalWhisperSTT:
    """Unit tests for local Faster-Whisper provider."""

    def test_language_normalization(self) -> None:
        stt = LocalWhisperSTT()
        assert stt._normalize_language("hinglish") == "hi"
        assert stt._normalize_language("hi-Latn") == "hi"
        assert stt._normalize_language("en-US") == "en"
        assert stt._normalize_language("auto") is None
        assert stt._normalize_language(None) is None

    def test_missing_dependency_raises_error(self) -> None:
        stt = LocalWhisperSTT(model_size_or_path="base")
        with patch.dict("sys.modules", {"faster_whisper": None}):
            with pytest.raises(ProviderUnavailableException):
                stt._ensure_loaded()

    @pytest.mark.asyncio
    async def test_transcribe_once_mocked(self) -> None:
        stt = LocalWhisperSTT(model_size_or_path="base")
        mock_segment = MagicMock()
        mock_segment.text = "Hello PIXEL how are you"
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.98
        mock_info.duration = 1.5

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        stt._model = mock_model
        stt._is_loaded = True

        fake_pcm = b"\x00\x00" * 16000  # 1 sec of silence
        res = await stt.transcribe_once(fake_pcm, language="en")

        assert res.is_final is True
        assert res.text == "Hello PIXEL how are you"
        assert res.language == "en"
        assert res.confidence == 0.98
        assert res.provider == "local_whisper"

    @pytest.mark.asyncio
    async def test_transcribe_stream_chunks(self) -> None:
        stt = LocalWhisperSTT(model_size_or_path="base")
        mock_segment = MagicMock()
        mock_segment.text = "Hello"
        mock_info = MagicMock()
        mock_info.language = "en"
        mock_info.language_probability = 0.95
        mock_info.duration = 1.0

        mock_model = MagicMock()
        mock_model.transcribe.return_value = ([mock_segment], mock_info)
        stt._model = mock_model
        stt._is_loaded = True

        async def _sample_stream() -> AsyncIterator[AudioFrame]:
            for i in range(2):
                yield AudioFrame(
                    sample_rate=16000,
                    channels=1,
                    pcm_data=b"\x00\x00" * 8000,  # 0.5s per frame
                    timestamp_ms=i * 500,
                )

        results = []
        async for event in stt.transcribe_stream(_sample_stream(), session_id="test-session"):
            results.append(event)

        assert len(results) >= 1
        assert results[-1].is_final is True
        assert results[-1].text == "Hello"


class TestCloudSTT:
    """Unit tests for Cloud STT provider."""

    def test_availability_check(self) -> None:
        cloud = CloudSTTProvider(api_key=None)
        assert not cloud.is_available()

        cloud_with_key = CloudSTTProvider(api_key="sk-test-key-12345")
        assert cloud_with_key.is_available()

    @pytest.mark.asyncio
    async def test_transcribe_unconfigured_raises(self) -> None:
        cloud = CloudSTTProvider(api_key=None)
        with pytest.raises(ProviderUnavailableException):
            await cloud.transcribe_once(b"\x00\x00" * 1600)


class TestHybridSTT:
    """Unit tests for Hybrid STT Provider."""

    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self) -> None:
        from unittest.mock import AsyncMock

        primary = LocalWhisperSTT()
        # force primary to fail
        primary.transcribe_once = AsyncMock(side_effect=RuntimeError("Local STT crash"))  # type: ignore

        from packages.contracts.events import TranscriptEvent

        fallback = MagicMock()
        fallback.transcribe_once = AsyncMock(
            return_value=TranscriptEvent(
                session_id="s1",
                text="Fallback transcript text",
                is_final=True,
                language="en",
                provider="cloud_stt",
            )
        )

        hybrid = HybridSTTProvider(primary_provider=primary, fallback_provider=fallback)
        result = await hybrid.transcribe_once(b"\x00\x00" * 1600)

        assert result.text == "Fallback transcript text"
        assert result.provider == "cloud_stt"
        fallback.transcribe_once.assert_called_once()
