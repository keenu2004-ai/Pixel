"""PIXEL — Phase 16 Sensitive Screen & Privacy Protection Unit Tests.

Validates detection of API keys, Passwords, OTPs, Payment Cards, and automated
privacy classification on screen frames.
"""

from packages.contracts.multimodal import (
    OCRBlock,
    OCRLine,
    OCRResult,
    ScreenFrame,
    VisualBoundingBox,
    VisualSensitivityType,
)
from services.multimodal.sensitive_screen_detector import SensitiveScreenDetector


def test_detect_api_key_and_secret() -> None:
    detector = SensitiveScreenDetector()
    box = VisualBoundingBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.2)
    line = OCRLine(text="Export OPENAI_API_KEY=sk-abcdef1234567890abcdef123456", bounding_box=box)
    block = OCRBlock(text=line.text, lines=[line], bounding_box=box)
    ocr = OCRResult(full_text=line.text, blocks=[block])

    regions = detector.detect_sensitive_regions(ocr)
    assert len(regions) == 1
    assert regions[0].is_sensitive is True
    assert regions[0].sensitivity_type == VisualSensitivityType.API_KEY_OR_SECRET
    assert regions[0].text_content == "[REDACTED_CONFIDENTIAL]"


def test_detect_otp_code() -> None:
    detector = SensitiveScreenDetector()
    box = VisualBoundingBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.2)
    line = OCRLine(text="Your verification OTP is 849201", bounding_box=box)
    block = OCRBlock(text=line.text, lines=[line], bounding_box=box)
    ocr = OCRResult(full_text=line.text, blocks=[block])

    regions = detector.detect_sensitive_regions(ocr)
    assert len(regions) == 1
    assert regions[0].sensitivity_type == VisualSensitivityType.OTP_OR_PIN


def test_screen_privacy_classification_window_title() -> None:
    detector = SensitiveScreenDetector()
    frame = ScreenFrame(window_title="1Password - Master Vault")
    classified = detector.process_screen(frame)

    assert classified.privacy_classified is True
    assert classified.has_sensitive_data is True
