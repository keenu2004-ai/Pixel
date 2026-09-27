"""Abstract Interface for Voice Activity Detection (VAD) Providers."""

from abc import ABC, abstractmethod

from packages.contracts.events import AudioFrame, VADEvent


class BaseVADProvider(ABC):
    """Abstract base provider for L0/L1 Voice Activity Detection."""

    @abstractmethod
    async def process_frame(self, frame: AudioFrame, session_id: str) -> VADEvent:
        """Processes an audio frame and returns VAD state classification."""
        pass

    @abstractmethod
    def reset(self, session_id: str) -> None:
        """Resets internal VAD state for a session."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Returns True if the underlying model/runtime is loaded and ready for inference."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Releases all model runtime sessions and memory resources."""
        pass
