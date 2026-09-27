"""Unit tests for PreferenceEngine (Explicit vs Inferred, Conflict Resolution, Explainability, Reversibility)."""

import pytest

from packages.contracts.personalization import (
    ConfidenceTier,
    ProvenanceType,
)
from services.personalization.preference_engine import PreferenceEngine
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def pref_engine() -> PreferenceEngine:
    store = UserModelStore(db_path=":memory:")
    return PreferenceEngine(user_model_store=store)


@pytest.mark.asyncio
async def test_set_explicit_preference(pref_engine: PreferenceEngine) -> None:
    rec = await pref_engine.set_explicit_preference(
        key="preferred_code_editor",
        value="Neovim",
        user_id="dev_1",
    )
    assert rec.key == "preferred_code_editor"
    assert rec.value == "Neovim"
    assert rec.confidence == 1.0
    assert rec.confidence_tier == ConfidenceTier.USER_CONFIRMED
    assert rec.provenance == ProvenanceType.EXPLICIT_USER

    profile = await pref_engine.get_preference_profile("dev_1")
    assert profile.preferred_code_editor == "Neovim"


@pytest.mark.asyncio
async def test_inferred_preference_cannot_override_explicit(
    pref_engine: PreferenceEngine,
) -> None:
    # 1. User explicitly sets custom editor
    await pref_engine.set_explicit_preference(
        key="favorite_terminal",
        value="wezterm",
        user_id="dev_2",
    )

    # 2. System tries to infer a different terminal based on observation
    inferred_rec = await pref_engine.record_inferred_preference(
        key="favorite_terminal",
        value="alacritty",
        confidence=0.85,
        user_id="dev_2",
    )
    # Must be rejected because explicit preference exists
    assert inferred_rec is None

    profile = await pref_engine.get_preference_profile("dev_2")
    assert profile.custom_preferences.get("favorite_terminal") == "wezterm"


@pytest.mark.asyncio
async def test_preference_conflict_resolution_newer_explicit_wins(
    pref_engine: PreferenceEngine,
) -> None:
    # Old explicit preference
    await pref_engine.set_explicit_preference(
        key="preferred_browser",
        value="edge",
        user_id="dev_3",
    )

    # Newer explicit preference (user changed mind)
    await pref_engine.set_explicit_preference(
        key="preferred_browser",
        value="chrome",
        user_id="dev_3",
    )

    profile = await pref_engine.get_preference_profile("dev_3")
    assert profile.preferred_browser == "chrome"


@pytest.mark.asyncio
async def test_explain_preference(pref_engine: PreferenceEngine) -> None:
    await pref_engine.set_explicit_preference(
        key="preferred_code_editor",
        value="Emacs",
        user_id="dev_4",
    )

    explanation = await pref_engine.explain_preference("preferred_code_editor", user_id="dev_4")
    assert explanation["status"] == "ACTIVE_EXPLICIT"
    assert explanation["is_explicit"] is True
    assert explanation["confidence"] == 1.0
    assert "Emacs" in explanation["explanation"]


@pytest.mark.asyncio
async def test_revert_preference(pref_engine: PreferenceEngine) -> None:
    await pref_engine.set_explicit_preference(
        key="custom_theme",
        value="nord",
        user_id="dev_5",
    )

    # Revert
    reverted = await pref_engine.revert_preference("custom_theme", user_id="dev_5")
    assert reverted is True

    profile = await pref_engine.get_preference_profile("dev_5")
    assert "custom_theme" not in profile.custom_preferences
