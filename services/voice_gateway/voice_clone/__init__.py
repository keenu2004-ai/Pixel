"""Personalized Voice Cloning & Speaker Modeling Module.

Provides neural speaker embedding extraction, authorized voice enrollment,
Indian-accent synthesis, and bilingual code-switching voice personalization.
"""

from services.voice_gateway.voice_clone.enrollment import VoiceEnrollmentManager
from services.voice_gateway.voice_clone.personalized_tts import PersonalizedTTSProvider
from services.voice_gateway.voice_clone.speaker_encoder import ECAPASpeakerEncoder

__all__ = [
    "ECAPASpeakerEncoder",
    "VoiceEnrollmentManager",
    "PersonalizedTTSProvider",
]
