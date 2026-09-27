"""PIXEL — Phase 16 Visual Verification Unit Tests.

Validates empirical before/after state diffing and post-execution state verification.
"""

from packages.contracts.multimodal import (
    ScreenSemanticModel,
    UIElement,
    VisualBoundingBox,
    VisualVerificationTarget,
)
from services.multimodal.visual_verifier import VisualActionVerifier


def test_visual_verification_element_transition_success() -> None:
    verifier = VisualActionVerifier()

    box = VisualBoundingBox(x_min=0.1, y_min=0.1, x_max=0.2, y_max=0.2)
    before_model = ScreenSemanticModel(
        window_title="Settings Window",
        screenshot_hash="hash_state_a",
        elements=[UIElement(label="Wi-Fi Toggle", bounding_box=box)],
    )

    after_model = ScreenSemanticModel(
        window_title="Settings - Wi-Fi Active",
        screenshot_hash="hash_state_b",
        elements=[
            UIElement(label="Wi-Fi Toggle", bounding_box=box),
            UIElement(label="Connected: PixelNet-5G", bounding_box=box),
        ],
    )

    target = VisualVerificationTarget(
        expected_element_label="Connected: PixelNet-5G",
        expected_text_contains="PixelNet-5G",
    )

    res = verifier.verify_transition(before_model, after_model, target)
    assert res.verified is True
    assert res.confidence >= 0.95


def test_visual_verification_failure_detection() -> None:
    verifier = VisualActionVerifier()

    box = VisualBoundingBox(x_min=0.1, y_min=0.1, x_max=0.2, y_max=0.2)
    before_model = ScreenSemanticModel(
        window_title="Editor",
        screenshot_hash="hash_state_a",
        elements=[],
    )

    # State after action did not produce expected dialog
    after_model = ScreenSemanticModel(
        window_title="Editor",
        screenshot_hash="hash_state_b",
        elements=[UIElement(label="Unrelated Button", bounding_box=box)],
    )

    target = VisualVerificationTarget(
        expected_element_label="Save Confirmation Dialog",
    )

    res = verifier.verify_transition(before_model, after_model, target)
    assert res.verified is False
    assert "not found" in res.explanation.lower()
