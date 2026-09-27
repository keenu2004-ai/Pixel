"""Abstract Interface for Speech-to-Text (STT) Providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from packages.contracts.events import AudioFrame, TranscriptEvent


class BaseSTTProvider(ABC):
    """Abstract base provider for L1 Speech-to-Text engines."""

    @abstractmethod
    def transcribe_stream(
        self,
        audio_stream: AsyncIterator[AudioFrame],
        session_id: str,
        language: str | None = None
    ) -> AsyncIterator[TranscriptEvent]:
        """Transcribes incoming audio frames yielding interim and final TranscriptEvents."""
        pass

    @abstractmethod
    async def transcribe_once(
        self,
        audio_bytes: bytes,
        language: str | None = None
    ) -> TranscriptEvent:
        """Transcribes a discrete audio buffer to a final transcript."""
        pass
