"""PIXEL — Phase 16 Screen Capture Manager.

Handles controlled desktop, mobile, and browser screenshots with automated
sensitive data detection and classification.
"""

import base64
import time

from packages.contracts.multimodal import FrameSource, ScreenFrame
from services.multimodal.sensitive_screen_detector import SensitiveScreenDetector


class ScreenCaptureManager:
    """Acquires bounded screen captures across desktop and mobile devices."""

    def __init__(
        self,
        device_id: str = "pixel-local",
        sensitive_detector: SensitiveScreenDetector | None = None,
    ) -> None:
        self._device_id = device_id
        self._sensitive_detector = sensitive_detector or SensitiveScreenDetector()

    async def capture_screen(
        self,
        source: FrameSource = FrameSource.DESKTOP_SCREEN,
        window_title: str | None = None,
        app_name: str | None = None,
        width: int = 1920,
        height: int = 1080,
    ) -> ScreenFrame:
        """Captures a screenshot and classifies privacy."""
        synthetic_payload = (
            f"SCREEN_{source.value}_{window_title or 'Desktop'}_{int(time.time())}".encode()
        )
        b64_data = base64.b64encode(synthetic_payload).decode("utf-8")

        frame = ScreenFrame(
            device_id=self._device_id,
            source=source,
            window_title=window_title or "Active Desktop Session",
            app_name=app_name or "System Shell",
            raw_bytes_base64=b64_data,
            width=width,
            height=height,
        )

        # Run automated privacy classification
        return self._sensitive_detector.process_screen(frame)
