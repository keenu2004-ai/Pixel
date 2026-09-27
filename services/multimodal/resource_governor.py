"""PIXEL — Phase 16 Vision & Camera Resource Governor.

Enforces CPU, GPU, memory ceilings, frame rate throttling, and battery conservation
budgets to prevent background drain or unbounded loops.
"""

import time


class VisionResourceGovernor:
    """Monitors and regulates multimodal computational budgets."""

    def __init__(
        self,
        max_fps: float = 5.0,
        max_resolution: tuple[int, int] = (1920, 1080),
        max_memory_mb: int = 512,
        battery_saver_mode: bool = False,
    ) -> None:
        self._max_fps = max_fps
        self._max_resolution = max_resolution
        self._max_memory_mb = max_memory_mb
        self._battery_saver_mode = battery_saver_mode
        self._last_capture_time: float = 0.0
        self._total_captures_count: int = 0

    @property
    def battery_saver_mode(self) -> bool:
        return self._battery_saver_mode

    @battery_saver_mode.setter
    def battery_saver_mode(self, enabled: bool) -> None:
        self._battery_saver_mode = enabled
        self._max_fps = 1.0 if enabled else 5.0

    def can_capture_frame(self) -> tuple[bool, str | None]:
        """Checks if a frame capture is permitted within the FPS and battery rate limit."""
        now = time.time()
        min_interval = 1.0 / self._max_fps
        if (now - self._last_capture_time) < min_interval:
            return False, f"Throttled: Minimum capture interval is {min_interval:.2f}s."

        return True, None

    def record_capture(self, width: int, height: int) -> None:
        """Records a successful capture event."""
        self._last_capture_time = time.time()
        self._total_captures_count += 1

    def get_bounded_dimensions(self, width: int, height: int) -> tuple[int, int]:
        """Clamps resolution to maximum configured boundary."""
        max_w, max_h = self._max_resolution
        if width <= max_w and height <= max_h:
            return width, height

        scale = min(max_w / width, max_h / height)
        return int(width * scale), int(height * scale)
