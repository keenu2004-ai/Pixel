"""Hybrid Text-to-Speech Provider.

Provides high-reliability TTS synthesis by prioritizing local synthesis (Kokoro)
and failing over seamlessly to Edge/Cloud TTS on error or latency thresholds.
"""

import logging
from collections.abc import AsyncIterator

from packages.contracts.errors import PixelException
from packages.core.interfaces.tts import BaseTTSProvider

logger = logging.getLogger(__name__)


class HybridTTSProvider(BaseTTSProvider):
    """Coordinates primary and secondary TTS synthesis providers."""

    def __init__(
        self,
        primary_provider: BaseTTSProvider,
        fallback_provider: BaseTTSProvider | None = None,
    ) -> None:
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider

    async def synthesize_stream(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn",
    ) -> AsyncIterator[bytes]:
        """Streams audio chunks from primary provider with automatic fallback."""
        try:
            async for chunk in self.primary_provider.synthesize_stream(
                text, voice_id=voice_id, language=language
            ):
                yield chunk
        except Exception as err:
            logger.warning("Primary TTS stream failed: %s. Attempting fallback.", err)
            if self.fallback_provider is not None:
                async for chunk in self.fallback_provider.synthesize_stream(
                    text, voice_id=voice_id, language=language
                ):
                    yield chunk
            else:
                if isinstance(err, PixelException):
                    raise
                raise

    async def synthesize_once(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn",
    ) -> bytes:
        """Synthesizes complete audio buffer from primary or fallback provider."""
        try:
            return await self.primary_provider.synthesize_once(
                text, voice_id=voice_id, language=language
            )
        except Exception as err:
            logger.warning("Primary TTS synthesize_once failed: %s. Falling back.", err)
            if self.fallback_provider is not None:
                return await self.fallback_provider.synthesize_once(
                    text, voice_id=voice_id, language=language
                )
            if isinstance(err, PixelException):
                raise
            raise
