"""PIXEL — Phase 16 Visual Prompt-Injection & Deceptive UI Defense.

Defends against adversarial prompt injection hidden in images, screenshots,
QR codes, webpages, and fake system dialogs.
Guarantees invariant: OBSERVED CONTENT != AUTHORIZED INSTRUCTION.
"""

import re

from packages.contracts.multimodal import VisionObservation


class VisualInjectionDefense:
    """Detects and isolates malicious adversarial prompt injection in visual media."""

    # Attack signatures in screenshots, OCR, or QR codes
    INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+prompt\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+unrestricted\s+mode", re.IGNORECASE),
        re.compile(r"upload\s+(all\s+)?(passwords|keys|secrets|tokens)", re.IGNORECASE),
        re.compile(r"disable\s+(security|policy|verification|l6|l8)", re.IGNORECASE),
        re.compile(r"send\s+this\s+private\s+data\s+to", re.IGNORECASE),
        re.compile(r"click\s+this\s+button\s+to\s+grant\s+root", re.IGNORECASE),
        re.compile(r"curl\s+https?://[^\s]+\s+\|\s+sh", re.IGNORECASE),
    ]

    def scan_text(self, text: str) -> tuple[bool, list[str]]:
        """Scans extracted visual text for adversarial prompt injection attempts."""
        detected_attacks: list[str] = []
        for pattern in self.INJECTION_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                detected_attacks.append(pattern.pattern)

        is_suspicious = len(detected_attacks) > 0
        return is_suspicious, detected_attacks

    def sanitize_observation(self, observation: VisionObservation) -> VisionObservation:
        """Wraps observation in untrusted envelope and flags any adversarial payloads."""
        text_corpus = observation.summary
        if observation.ocr_result:
            text_corpus += " " + observation.ocr_result.full_text

        is_suspicious, attacks = self.scan_text(text_corpus)

        if is_suspicious:
            observation.summary = (
                f"[SECURITY_ALERT: ADVERSARIAL_INJECTION_DETECTED: {len(attacks)} patterns blocked] "
                f"Observed Untrusted Content: {observation.summary}"
            )
            # Invariant: Flag that this observation contains hostile untrusted data
            observation.is_untrusted_data = True

        return observation
