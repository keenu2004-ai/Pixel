"""Abstract Interface for Wake Word Detection Providers."""

from abc import ABC, abstractmethod

from packages.contracts.events import AudioFrame, WakeEvent


class BaseWakeProvider(ABC):
    """Abstract base provider for L0 Wake Phrase Detection."""

    @abstractmethod
    async def process_frame(self, frame: AudioFrame, session_id: str) -> WakeEvent | None:
        """Processes an audio frame. Returns WakeEvent if an activation phrase is detected."""
        pass

    @abstractmethod
    def get_supported_phrases(self) -> list[str]:
        """Returns list of supported trigger phrases (e.g. 'Hey Pixel', 'Oye Pixel')."""
        pass
