"""Unit tests for CorrectionLearner (Correction Detection, Preference Update, Undo Stack)."""

import pytest

from packages.contracts.personalization import CorrectionType
from services.personalization.correction_learner import CorrectionLearner
from services.personalization.preference_engine import PreferenceEngine
from services.personalization.user_model_store import UserModelStore


@pytest.fixture
def correction_learner() -> CorrectionLearner:
    store = UserModelStore(db_path=":memory:")
    pe = PreferenceEngine(user_model_store=store)
    return CorrectionLearner(preference_engine=pe)


@pytest.mark.asyncio
async def test_detect_and_apply_browser_correction(
    correction_learner: CorrectionLearner,
) -> None:
    # User corrects: "No, I meant Edge"
    event = await correction_learner.detect_and_apply_correction(
        user_utterance="No, I meant Edge for my browser",
        session_id="s_corr_1",
        previous_assistant_response="I opened Chrome.",
        user_id="u_corr",
    )
    assert event is not None
    assert event.target_key == "preferred_browser"
    assert "edge" in str(event.new_value).lower()
    assert event.applied is True

    # Verify updated in preference engine
    profile = await correction_learner.preference_engine.get_preference_profile("u_corr")
    assert profile.preferred_browser == event.new_value


@pytest.mark.asyncio
async def test_undo_last_correction(correction_learner: CorrectionLearner) -> None:
    # 1. Apply correction
    await correction_learner.detect_and_apply_correction(
        user_utterance="Actually my code editor is PyCharm",
        session_id="s_corr_2",
        user_id="u_undo",
    )

    profile_before = await correction_learner.preference_engine.get_preference_profile("u_undo")
    assert profile_before.preferred_code_editor == "PyCharm"

    # 2. Undo correction
    undo_event = await correction_learner.undo_last_correction(user_id="u_undo")
    assert undo_event is not None
    assert undo_event.correction_type == CorrectionType.REVERT_LAST
