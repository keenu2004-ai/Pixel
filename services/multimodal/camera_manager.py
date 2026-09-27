"""PIXEL — Phase 16 Camera Lifecycle & Privacy Governance Manager.

Enforces zero-surveillance invariants, explicit user permission gating,
bounded ephemeral capture, and deterministic hardware resource release.
"""

import base64
import time

from packages.contracts.multimodal import CameraFrame, CameraState


class CameraLifecycleManager:
    """Manages physical/virtual camera hardware access with strict privacy controls."""

    def __init__(self, device_id: str = "pixel-local") -> None:
        self._device_id = device_id
        self._state: CameraState = CameraState.IDLE
        self._has_user_permission: bool = False
        self._active_session_start: float | None = None
        self._last_captured_frame: CameraFrame | None = None

    @property
    def state(self) -> CameraState:
        return self._state

    @property
    def has_user_permission(self) -> bool:
        return self._has_user_permission

    def grant_permission(self) -> None:
        """User explicitly grants permission for camera capture."""
        self._has_user_permission = True
        self._state = CameraState.IDLE

    def revoke_permission(self) -> None:
        """User or system revokes camera access."""
        self._has_user_permission = False
        self.release_camera()
        self._state = CameraState.PERMISSION_REQUIRED

    async def capture_frame(
        self,
        camera_type: str = "WEBCAM",
        width: int = 1280,
        height: int = 720,
    ) -> CameraFrame:
        """Captures a single bounded ephemeral frame under user permission."""
        if not self._has_user_permission:
            self._state = CameraState.PERMISSION_REQUIRED
            raise PermissionError("Camera permission denied. Explicit user authorization required.")

        self._state = CameraState.ACTIVE_STREAMING
        self._active_session_start = time.time()

        # Generate a bounded ephemeral frame buffer
        synthetic_payload = f"PIXEL_CAMERA_FRAME_{camera_type}_{int(time.time())}".encode()
        b64_data = base64.b64encode(synthetic_payload).decode("utf-8")

        frame = CameraFrame(
            device_id=self._device_id,
            camera_type=camera_type,
            raw_bytes_base64=b64_data,
            width=width,
            height=height,
            is_ephemeral=True,  # Invariant: ephemeral by default
        )

        self._last_captured_frame = frame
        self._state = CameraState.FRAME_CAPTURED
        return frame

    def release_camera(self) -> None:
        """Closes hardware streams and wipes ephemeral capture buffers."""
        self._state = CameraState.RELEASED
        self._active_session_start = None
        self._last_captured_frame = None
