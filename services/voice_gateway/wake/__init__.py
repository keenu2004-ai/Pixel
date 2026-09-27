"""Wake Phrase Detection Service Package."""

from services.voice_gateway.wake.openwakeword_provider import (
    OpenWakeWordConfig,
    OpenWakeWordProvider,
    WakeWordModelIntegrityError,
)

__all__ = [
    "OpenWakeWordProvider",
    "OpenWakeWordConfig",
    "WakeWordModelIntegrityError",
]
