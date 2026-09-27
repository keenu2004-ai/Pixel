"""Microsoft Edge TTS Streaming Provider.

Provides high-quality, low-latency multilingual speech synthesis (Hindi, Hinglish, English)
with asynchronous streaming chunk output.
"""

import logging
from collections.abc import AsyncIterator

from packages.contracts.errors import ProviderUnavailableException
from packages.core.interfaces.tts import BaseTTSProvider

logger = logging.getLogger(__name__)

# Standard voice mapping for Hindi, Hinglish, English
DEFAULT_VOICES = {
    "en": "en-US-JennyNeural",
    "en-in": "en-IN-NeerjaNeural",
    "hi": "hi-IN-SwaraNeural",
    "hi-latn": "hi-IN-MadhurNeural",
    "hinglish": "hi-IN-MadhurNeural",
}


class EdgeTTSProvider(BaseTTSProvider):
    """Asynchronous Edge TTS provider with streaming audio chunk output."""

    def __init__(
        self,
        default_voice: str = "hi-IN-MadhurNeural",
        default_language: str = "hi-Latn",
        rate: str = "+0%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.default_voice = default_voice
        self.default_language = default_language
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    def is_available(self) -> bool:
        """Checks if edge_tts package is available."""
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def _resolve_voice(self, voice_id: str | None, language: str) -> str:
        """Resolves target voice string based on voice_id or language."""
        if voice_id:
            return voice_id
        lang_key = language.lower().strip()
        return DEFAULT_VOICES.get(lang_key, self.default_voice)

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn",
    ) -> AsyncIterator[bytes]:
        """Synthesizes text and yields audio byte chunks as they arrive from edge_tts."""
        if not text or not text.strip():
            return

        try:
            import edge_tts
        except ImportError as err:
            raise ProviderUnavailableException("edge-tts package is not installed.") from err

        target_voice = self._resolve_voice(voice_id, language)
        communicate = edge_tts.Communicate(
            text=text.strip(),
            voice=target_voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch,
        )

        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    data: bytes = chunk["data"]
                    if data:
                        yield data
        except Exception as err:
            logger.error("Edge TTS streaming failed: %s", err)
            raise

    async def synthesize_once(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn",
    ) -> bytes:
        """Synthesizes text into a single complete audio byte buffer."""
        if not text or not text.strip():
            return b""

        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text, voice_id=voice_id, language=language):
            chunks.append(chunk)
        return b"".join(chunks)
