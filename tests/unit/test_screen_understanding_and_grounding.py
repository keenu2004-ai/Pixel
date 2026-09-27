"""PIXEL — Phase 16 Screen Understanding & UI Grounding Unit Tests.

Validates semantic hierarchy parsing, button and text field detection,
and zero-guessing UI grounding (exact match, partial match, ambiguity handling, low confidence).
"""

import pytest

from packages.contracts.multimodal import (
    ScreenFrame,
    ScreenSemanticModel,
    UIElement,
    UIElementType,
    VisualBoundingBox,
)
from services.multimodal.screen_understanding import ScreenSemanticAnalyzer
from services.multimodal.ui_grounding import UIGroundingEngine


@pytest.mark.asyncio
async def test_screen_semantic_analyzer_defaults() -> None:
    analyzer = ScreenSemanticAnalyzer()
    frame = ScreenFrame(window_title="Settings - System", app_name="SettingsApp")
    model = await analyzer.analyze_screen(frame)

    assert model.app_name == "SettingsApp"
    assert model.window_title == "Settings - System"
    assert len(model.elements) >= 3
    assert any(el.label == "Settings" for el in model.elements)


@pytest.mark.asyncio
async def test_ui_grounding_exact_and_partial_match() -> None:
    analyzer = ScreenSemanticAnalyzer()
    grounding = UIGroundingEngine()

    frame = ScreenFrame(window_title="Main Desktop")
    model = await analyzer.analyze_screen(frame)

    # 1. English direct intent
    target = await grounding.ground_target(model, "Settings")
    assert target is not None
    assert target.is_ambiguous is False
    assert target.label == "Settings"
    assert target.target_coordinates[0] > 0
    assert target.target_coordinates[1] > 0

    # 2. Hinglish action intent: "Settings button pe click karo"
    target_hinglish = await grounding.ground_target(model, "Settings button pe click karo")
    assert target_hinglish is not None
    assert target_hinglish.is_ambiguous is False
    assert target_hinglish.label == "Settings"


@pytest.mark.asyncio
async def test_ui_grounding_ambiguity_no_guessing() -> None:
    grounding = UIGroundingEngine()

    # Create screen model with 2 identical "Submit" buttons
    box1 = VisualBoundingBox(
        x_min=0.1,
        y_min=0.1,
        x_max=0.2,
        y_max=0.2,
        abs_x=100,
        abs_y=100,
        abs_width=50,
        abs_height=20,
    )
    box2 = VisualBoundingBox(
        x_min=0.8,
        y_min=0.8,
        x_max=0.9,
        y_max=0.9,
        abs_x=800,
        abs_y=800,
        abs_width=50,
        abs_height=20,
    )

    model = ScreenSemanticModel(
        elements=[
            UIElement(label="Submit", bounding_box=box1, element_type=UIElementType.BUTTON),
            UIElement(label="Submit", bounding_box=box2, element_type=UIElementType.BUTTON),
        ]
    )

    # Invariant Rule 22: NEVER CLICK BY GUESS — Multiple matching elements -> Ask clarification
    target = await grounding.ground_target(model, "Submit")
    assert target is not None
    assert target.is_ambiguous is True
    assert target.candidate_matches_count == 2
    assert target.confidence <= 0.5


@pytest.mark.asyncio
async def test_ui_grounding_not_found() -> None:
    grounding = UIGroundingEngine()
    model = ScreenSemanticModel(elements=[])
    target = await grounding.ground_target(model, "NonExistentButton")
    assert target is None
