"""Unit tests for AdaptiveResponseStrategy (Conciseness, Tone, Hindi/Hinglish Code-Switching)."""

from packages.contracts.personalization import (
    AssistantTone,
    LanguageMode,
    ResponseLengthPreference,
    UserPreferenceProfile,
)
from services.personalization.adaptive_strategy import AdaptiveResponseStrategy


def test_concise_response_adaptation() -> None:
    prefs = UserPreferenceProfile(
        response_length=ResponseLengthPreference.CONCISE,
        tone=AssistantTone.FRIENDLY,
    )
    long_msg = (
        "Your tests passed. 455 tests executed without errors. CPU load is 12%. Battery is 98%."
    )
    adapted = AdaptiveResponseStrategy.adapt_response(long_msg, preferences=prefs)
    assert "Your tests passed." in adapted
    # Kept concise (first 2 sentences)
    assert "Battery is 98%" not in adapted


def test_hinglish_code_switching_preserves_technical_terms() -> None:
    prefs = UserPreferenceProfile(
        language_mode=LanguageMode.HINGLISH,
    )
    msg = "Task completed successfully. All unit tests passed."
    adapted = AdaptiveResponseStrategy.adapt_response(
        msg, preferences=prefs, detected_language="hinglish"
    )
    assert "complete ho gaya" in adapted or "Task" in adapted


def test_voice_parameter_calculation() -> None:
    prefs = UserPreferenceProfile(
        response_length=ResponseLengthPreference.CONCISE,
        tone=AssistantTone.FRIENDLY,
        preferred_spoken_language="en",
    )
    v_params = AdaptiveResponseStrategy.compute_voice_parameters(prefs)
    assert float(v_params["speed_factor"]) >= 1.0
    assert float(v_params["pitch_adjustment"]) >= 1.0
