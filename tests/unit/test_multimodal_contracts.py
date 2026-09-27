"""PIXEL — Phase 16 Multimodal Contracts Unit Tests.

Validates schemas, geometry math, center point calculations, serialization,
and untrusted data envelope invariants.
"""

from packages.contracts.multimodal import (
    CameraFrame,
    OCRBlock,
    OCRLine,
    OCRResult,
    OCRWord,
    UIElement,
    UIElementType,
    VisualActionTarget,
    VisualBoundingBox,
    VisualMemoryCategory,
    VisualMemoryRecord,
)


def test_visual_bounding_box_center_point() -> None:
    box = VisualBoundingBox(
        x_min=0.1,
        y_min=0.2,
        x_max=0.3,
        y_max=0.4,
        abs_x=100,
        abs_y=200,
        abs_width=100,
        abs_height=100,
    )
    cx, cy = box.center_point()
    assert cx == 150
    assert cy == 250


def test_ui_element_defaults_and_contracts() -> None:
    box = VisualBoundingBox(x_min=0.0, y_min=0.0, x_max=0.5, y_max=0.5)
    element = UIElement(
        element_type=UIElementType.BUTTON,
        label="Confirm Order",
        bounding_box=box,
        confidence=0.98,
    )
    assert element.is_interactive is True
    assert element.confidence == 0.98
    assert element.element_type == UIElementType.BUTTON


def test_ocr_result_untrusted_data_invariant() -> None:
    box = VisualBoundingBox(x_min=0.0, y_min=0.0, x_max=0.5, y_max=0.5)
    word = OCRWord(text="Hello", bounding_box=box)
    line = OCRLine(text="Hello World", words=[word], bounding_box=box)
    block = OCRBlock(text="Hello World", lines=[line], bounding_box=box)

    ocr = OCRResult(
        full_text="Hello World",
        blocks=[block],
        detected_languages=["en"],
    )
    assert ocr.is_untrusted_data is True  # Non-negotiable safety invariant


def test_camera_frame_ephemeral_invariant() -> None:
    frame = CameraFrame(
        device_id="mobile_01",
        camera_type="FRONT",
        raw_bytes_base64="dGVzdA==",
    )
    assert frame.is_ephemeral is True


def test_visual_memory_record_expiration() -> None:
    record = VisualMemoryRecord(
        key="repo_diagram",
        value_summary="Architecture layout of Pixel",
        category=VisualMemoryCategory.TEMPORARY_CONTEXT,
        ttl_seconds=0,  # Expired immediately
    )
    assert record.is_expired() is True


def test_visual_action_target_ambiguity_flag() -> None:
    target = VisualActionTarget(
        element_id="el_123",
        label="Submit",
        element_type=UIElementType.BUTTON,
        target_coordinates=(100, 200),
        confidence=0.5,
        is_ambiguous=True,
        candidate_matches_count=2,
    )
    assert target.is_ambiguous is True
    assert target.candidate_matches_count == 2
