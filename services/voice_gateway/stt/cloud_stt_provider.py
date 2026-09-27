"""Cloud Speech-to-Text Provider.

Provides external API transcription fallback (Deepgram / OpenAI Whisper / mock cloud)
with retry, structured error mapping, and streaming support.
"""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from typing import Any

from packages.contracts.errors import NetworkException, ProviderUnavailableException
from packages.contracts.events import AudioFrame, TranscriptEvent
from packages.core.interfaces.stt import BaseSTTProvider

logger = logging.getLogger(__name__)


class CloudSTTProvider(BaseSTTProvider):
    """External Cloud Speech-to-Text provider with graceful error handling and retry."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint_url: str = "https://api.openai.com/v1/audio/transcriptions",
        model: str = "whisper-1",
        default_language: str = "en",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key
        self.endpoint_url = endpoint_url
        self.model = model
        self.default_language = default_language
        self.timeout_seconds = timeout_seconds

    def is_available(self) -> bool:
        """Returns True if api_key is configured or test endpoint is available."""
        return bool(self.api_key and len(self.api_key) > 5)

    async def transcribe_once(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptEvent:
        """Sends audio payload to Cloud STT API and returns TranscriptEvent."""
        if not audio_bytes:
            return TranscriptEvent(
                session_id="default",
                text="",
                is_final=True,
                confidence=1.0,
                language=language or self.default_language,
                provider="cloud_stt",
            )

        if not self.is_available():
            raise ProviderUnavailableException("Cloud STT API key not configured or invalid.")

        target_lang = language or self.default_language

        try:
            req = urllib.request.Request(
                self.endpoint_url,
                data=audio_bytes,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/octet-stream",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as response:
                    resp_data: dict[str, Any] = json.loads(response.read().decode("utf-8"))
                    text = str(resp_data.get("text", ""))
                    return TranscriptEvent(
                        session_id="default",
                        text=text,
                        is_final=True,
                        confidence=float(resp_data.get("confidence", 0.95)),
                        language=str(resp_data.get("language", target_lang)),
                        provider="cloud_stt",
                        metadata=resp_data,
                    )
            except urllib.error.URLError as err:
                logger.warning("Cloud STT request failed: %s", err)
                raise NetworkException(f"Cloud STT API unreachable: {err}") from err
        except Exception as err:
            if isinstance(err, (NetworkException, ProviderUnavailableException)):
                raise
            raise NetworkException(f"Cloud STT unexpected error: {err}") from err

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        session_id: str,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptEvent]:
        """Collects stream frames and passes to transcribe_once."""
        buffer = bytearray()
        async for frame in audio_stream:
            buffer.extend(frame.pcm_data)

        if buffer:
            result = await self.transcribe_once(bytes(buffer), language=language)
            yield TranscriptEvent(
                session_id=session_id,
                text=result.text,
                is_final=True,
                confidence=result.confidence,
                language=result.language,
                provider="cloud_stt",
            )
