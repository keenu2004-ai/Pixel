"""Abstract Interface for Text-to-Speech (TTS) Providers."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseTTSProvider(ABC):
    """Abstract base provider for L1 Text-to-Speech synthesis engines."""

    @abstractmethod
    def synthesize_stream(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn"
    ) -> AsyncIterator[bytes]:
        """Synthesizes input text yielding streaming PCM or Opus audio chunks."""
        pass

    @abstractmethod
    async def synthesize_once(
        self,
        text: str,
        voice_id: str | None = None,
        language: str = "hi-Latn"
    ) -> bytes:
        """Synthesizes input text to a complete audio byte buffer."""
        pass
