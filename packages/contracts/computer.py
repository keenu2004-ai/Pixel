"""Desktop Computer Control and Visual State Contracts."""

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class WindowBounds(BaseModel):
    """Screen coordinate bounding box for an application window."""

    x: int = Field(default=0, description="X coordinate of top-left corner")
    y: int = Field(default=0, description="Y coordinate of top-left corner")
    width: int = Field(default=1920, ge=1, description="Window width in pixels")
    height: int = Field(default=1080, ge=1, description="Window height in pixels")


class WindowState(BaseModel):
    """Metadata describing an open desktop application window."""

    window_id: str = Field(
        default_factory=_gen_id, description="Handle or unique window identifier"
    )
    title: str = Field(..., description="Window title bar string")
    app_name: str = Field(..., description="Executable / process name (e.g. Code, chrome, notepad)")
    is_active: bool = Field(
        default=False, description="Whether this window currently has keyboard/mouse focus"
    )
    is_minimized: bool = Field(default=False, description="Whether window is minimized")
    bounds: WindowBounds = Field(default_factory=WindowBounds, description="Window screen geometry")


class ScreenshotPayload(BaseModel):
    """Visual capture payload of active window or permitted display area."""

    capture_id: str = Field(default_factory=_gen_id, description="Unique capture identifier")
    window_id: str | None = Field(default=None, description="Window ID if window-scoped")
    app_name: str | None = Field(default=None, description="Application name captured")
    format: str = Field(default="png", description="Image encoding format (png, webp, jpeg)")
    width: int = Field(default=1920, ge=1)
    height: int = Field(default=1080, ge=1)
    data_base64: str = Field(
        default="", description="Base64-encoded image bytes or placeholder in mock"
    )
    is_redacted: bool = Field(
        default=True, description="Whether sensitive visual regions are masked"
    )
    timestamp: datetime = Field(default_factory=_utc_now)


class ClipboardData(BaseModel):
    """System clipboard contents."""

    text: str = Field(default="", description="Text content on clipboard")
    mime_type: str = Field(default="text/plain", description="MIME format of clipboard content")
    length: int = Field(default=0, ge=0, description="Character count")
    timestamp: datetime = Field(default_factory=_utc_now)
