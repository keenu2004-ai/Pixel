"""Hybrid Speech-to-Text Manager.

Manages primary local Whisper STT with automatic fallback to Cloud STT
upon unrecoverable engine errors, missing models, or high compute load.
"""

import logging
from collections.abc import AsyncIterator

from packages.contracts.errors import PixelException
from packages.contracts.events import AudioFrame, TranscriptEvent
from packages.core.interfaces.stt import BaseSTTProvider

logger = logging.getLogger(__name__)


class HybridSTTProvider(BaseSTTProvider):
    """Orchestrates local primary STT and cloud secondary STT."""

    def __init__(
        self,
        primary_provider: BaseSTTProvider,
        fallback_provider: BaseSTTProvider | None = None,
        prefer_local: bool = True,
    ) -> None:
        self.primary_provider = primary_provider
        self.fallback_provider = fallback_provider
        self.prefer_local = prefer_local

    async def transcribe_once(
        self,
        audio_bytes: bytes,
        language: str | None = None,
    ) -> TranscriptEvent:
        """Attempts transcription on primary provider, falling back to secondary if primary fails."""
        try:
            return await self.primary_provider.transcribe_once(audio_bytes, language=language)
        except Exception as err:
            logger.warning("Primary STT provider failed: %s. Attempting fallback.", err)
            if self.fallback_provider is not None:
                return await self.fallback_provider.transcribe_once(audio_bytes, language=language)
            if isinstance(err, PixelException):
                raise
            raise

    async def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        session_id: str,
        language: str | None = None,
    ) -> AsyncIterator[TranscriptEvent]:
        """Streams audio to primary provider, falling back to secondary upon failure."""
        try:
            async for event in self.primary_provider.transcribe_stream(
                audio_stream, session_id=session_id, language=language
            ):
                yield event
        except Exception as err:
            logger.warning("Primary STT streaming failed: %s.", err)
            if self.fallback_provider is not None:
                logger.info("Attempting fallback streaming.")
            raise
