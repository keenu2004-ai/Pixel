"""PIXEL — Phase 16 Sensitive Screen & Privacy Region Detector.

Identifies passwords, API keys, OTPs, credit cards, access tokens, and private
messages in visual screens and images to enforce local containment and redaction.
"""

import re

from packages.contracts.multimodal import (
    OCRResult,
    ScreenFrame,
    VisualRegion,
    VisualSensitivityType,
)


class SensitiveScreenDetector:
    """Detects and redacts confidential visual data."""

    # Regex patterns for sensitive credentials & tokens
    PATTERNS: dict[VisualSensitivityType, list[re.Pattern[str]]] = {
        VisualSensitivityType.API_KEY_OR_SECRET: [
            re.compile(r"sk-[a-zA-Z0-9]{20,}", re.IGNORECASE),
            re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
            re.compile(r"AKIA[0-9A-Z]{16}", re.IGNORECASE),
            re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]{20,}", re.IGNORECASE),
            re.compile(r"password\s*[:=]\s*['\"]?[^\s'\"]+['\"]?", re.IGNORECASE),
        ],
        VisualSensitivityType.OTP_OR_PIN: [
            re.compile(r"(?:otp|verification|code|pin)[^\d\n]{0,15}\b\d{4,8}\b", re.IGNORECASE),
            re.compile(r"\b\d{4,8}\b[^\d\n]{0,15}(?:otp|verification|code|pin)", re.IGNORECASE),
        ],
        VisualSensitivityType.PAYMENT_CARD: [
            re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b"),  # Standard 16-digit card
        ],
        VisualSensitivityType.PASSWORD: [
            re.compile(r"pwd|password|secret|credential", re.IGNORECASE),
        ],
    }

    def detect_sensitive_regions(
        self,
        ocr_result: OCRResult,
    ) -> list[VisualRegion]:
        """Scans OCR blocks for sensitive credentials and tokens."""
        sensitive_regions: list[VisualRegion] = []

        for block in ocr_result.blocks:
            for line in block.lines:
                for sens_type, regex_list in self.PATTERNS.items():
                    for pattern in regex_list:
                        if pattern.search(line.text):
                            region = VisualRegion(
                                label=f"Sensitive {sens_type.value}",
                                bounding_box=line.bounding_box,
                                confidence=0.99,
                                is_sensitive=True,
                                sensitivity_type=sens_type,
                                text_content="[REDACTED_CONFIDENTIAL]",
                            )
                            sensitive_regions.append(region)
                            break  # Found match on this line

        return sensitive_regions

    def process_screen(
        self,
        screen: ScreenFrame,
        ocr_result: OCRResult | None = None,
    ) -> ScreenFrame:
        """Classifies screen frame and applies sensitivity flags."""
        has_sensitive = False

        # 1. Window title heuristics (e.g., password manager, incognito, auth dialog)
        if screen.window_title:
            title_lower = screen.window_title.lower()
            if any(
                k in title_lower
                for k in ["1password", "bitwarden", "keepass", "authenticator", "incognito"]
            ):
                has_sensitive = True

        # 2. OCR content scan
        if ocr_result:
            regions = self.detect_sensitive_regions(ocr_result)
            if regions:
                has_sensitive = True

        screen.privacy_classified = True
        screen.has_sensitive_data = has_sensitive
        return screen
