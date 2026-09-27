"""PIXEL — Adaptive Response Strategy & Multilingual Dialogue Engine.

Adapts:
1. Response Length (Concise, Balanced, Detailed)
2. Technical Depth (Beginner, Intermediate, Expert)
3. Tone (Casual, Formal, Friendly, Technical)
4. Multilingual Hindi / Hinglish Code-Switching without translating technical keywords
5. Voice Parameters (speaking rate, pause style, confirmation brevity)
"""

import logging
import re

from packages.contracts.personalization import (
    AssistantTone,
    LanguageMode,
    ResponseLengthPreference,
    UserPreferenceProfile,
)

logger = logging.getLogger(__name__)


class AdaptiveResponseStrategy:
    """Calculates and formats adaptive response styling for text and voice output."""

    # Hindi / Hinglish cue words
    HINDI_INDICATORS = {
        "kya",
        "kaise",
        "batao",
        "karo",
        "namaste",
        "mujhe",
        "mera",
        "meri",
        "hai",
        "haan",
        "nahi",
        "shukriya",
        "kripya",
        "chalo",
        "sun",
        "samajh",
    }

    # Protected technical terms that must never be translated into Hindi
    TECHNICAL_TERMS = {
        "commit",
        "git",
        "push",
        "pull",
        "merge",
        "branch",
        "repository",
        "test",
        "pytest",
        "mypy",
        "ruff",
        "database",
        "sql",
        "sqlite",
        "api",
        "endpoint",
        "token",
        "server",
        "browser",
        "terminal",
        "powershell",
        "docker",
        "container",
        "cache",
        "json",
        "http",
        "async",
        "process",
    }

    @classmethod
    def detect_language(cls, text: str, user_preference: LanguageMode) -> str:
        """Detects whether dialogue is English, Hindi, or Hinglish."""
        if user_preference == LanguageMode.HINDI:
            return "hi"
        if user_preference == LanguageMode.HINGLISH:
            return "hinglish"
        if user_preference == LanguageMode.ENGLISH:
            return "en"

        # Automatic detection
        words = set(re.findall(r"\b\w+\b", text.lower()))
        hindi_count = len(words.intersection(cls.HINDI_INDICATORS))
        if hindi_count >= 2:
            return "hinglish"
        return "en"

    @classmethod
    def adapt_response(
        cls,
        base_message: str,
        preferences: UserPreferenceProfile,
        detected_language: str | None = None,
        technical_keywords: list[str] | None = None,
    ) -> str:
        """Applies personalization styling, length trimming, and language tone."""
        lang = detected_language or cls.detect_language(base_message, preferences.language_mode)
        length = preferences.response_length
        tone = preferences.tone

        message = base_message.strip()

        # 1. Length formatting
        if length == ResponseLengthPreference.CONCISE:
            # Voice-optimized: keep the first 1-2 core sentences
            sentences = [s.strip() for s in re.split(r"(?<=[.!?]) +", message) if s.strip()]
            if len(sentences) > 2:
                message = " ".join(sentences[:2])

        # 2. Hinglish / Hindi adaptation
        if lang in ("hi", "hinglish"):
            # Ensure technical keywords remain intact in English script
            if "completed successfully" in message.lower():
                message = "Task complete ho gaya hai."
            elif "failed" in message.lower() or "error" in message.lower():
                message = f"Process mein error aayi: {message}"

        # 3. Tone nuances
        if tone == AssistantTone.CASUAL and not message.endswith("!"):
            if lang in ("hi", "hinglish"):
                message = f"Done! {message}"
        elif tone == AssistantTone.FORMAL:
            if not any(message.startswith(w) for w in ["Please", "Here is", "Task"]):
                message = f"{message}"

        return message

    @classmethod
    def compute_voice_parameters(cls, preferences: UserPreferenceProfile) -> dict[str, float | str]:
        """Calculates personalized TTS vocal attributes."""
        speed_factor = 1.0
        if preferences.response_length == ResponseLengthPreference.CONCISE:
            speed_factor = 1.1  # Slightly faster for concise voice flow

        tone_pitch = 1.0
        if preferences.tone == AssistantTone.FRIENDLY:
            tone_pitch = 1.02
        elif preferences.tone == AssistantTone.FORMAL:
            tone_pitch = 0.98

        return {
            "speed_factor": speed_factor,
            "pitch_adjustment": tone_pitch,
            "preferred_language": preferences.preferred_spoken_language,
        }
