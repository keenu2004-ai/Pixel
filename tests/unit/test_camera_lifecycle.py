"""PIXEL — Phase 16 Camera Lifecycle & Resource Governor Unit Tests.

Validates explicit permission gating, state transitions, ephemeral frame capture,
hardware release, and resource limits.
"""

import pytest

from packages.contracts.multimodal import CameraState
from services.multimodal.camera_manager import CameraLifecycleManager
from services.multimodal.resource_governor import VisionResourceGovernor


@pytest.mark.asyncio
async def test_camera_permission_denial_by_default() -> None:
    camera = CameraLifecycleManager(device_id="desktop_01")
    assert camera.has_user_permission is False

    # Attempting capture without explicit user permission raises PermissionError
    with pytest.raises(PermissionError):
        await camera.capture_frame()

    final_state: CameraState = camera.state
    assert final_state == CameraState.PERMISSION_REQUIRED


@pytest.mark.asyncio
async def test_camera_authorized_capture_and_release() -> None:
    camera = CameraLifecycleManager(device_id="desktop_01")
    camera.grant_permission()
    assert camera.has_user_permission is True

    frame = await camera.capture_frame(camera_type="WEBCAM")
    assert frame.is_ephemeral is True

    camera.release_camera()
    final_state: CameraState = camera.state
    assert final_state == CameraState.RELEASED


def test_resource_governor_fps_throttling_and_battery() -> None:
    governor = VisionResourceGovernor(max_fps=2.0)
    assert governor.battery_saver_mode is False

    can_cap, err = governor.can_capture_frame()
    assert can_cap is True

    governor.record_capture(1920, 1080)
    # Immediately trying again should throttle
    can_cap_again, err2 = governor.can_capture_frame()
    assert can_cap_again is False
    assert "Throttled" in (err2 or "")

    # Enable battery saver mode
    governor.battery_saver_mode = True
    assert governor.battery_saver_mode is True

    # Test dimension clamping
    w, h = governor.get_bounded_dimensions(3840, 2160)
    assert w <= 1920
    assert h <= 1080
