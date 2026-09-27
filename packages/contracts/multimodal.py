"""PIXEL — Phase 16 Multimodal Perception, Vision & World Understanding Contracts.

Defines schemas and enums for:
1. Multimodal Frames (Camera, Screen, Browser, Document, Image).
2. Visual Grounding, Bounding Boxes, Normalized Coordinates, and UI Elements.
3. Multilingual OCR Structures (Hindi, Hinglish, English, Code, URLs).
4. Structured Screen Semantic Models and Application State.
5. Sensitive Region Detection & Privacy Redaction Envelopes.
6. Visual Verification Targets, Before/After Screenshot Diffing, and Transition State.
7. Visual Memory Records, Provenance, TTL, and Right-to-Forget Purging.
8. Multimodal Context Payloads and Untrusted Data Envelopes.
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# 1. Modality, Source & Lifecycle Enums
# ============================================================================


class ModalityType(StrEnum):
    """Supported multimodal input channels."""

    VOICE = "VOICE"
    IMAGE = "IMAGE"
    CAMERA = "CAMERA"
    SCREEN = "SCREEN"
    BROWSER = "BROWSER"
    DOCUMENT = "DOCUMENT"


class FrameSource(StrEnum):
    """Origin device or hardware sensor producing visual frames."""

    DESKTOP_SCREEN = "DESKTOP_SCREEN"
    ANDROID_SCREEN = "ANDROID_SCREEN"
    BROWSER_TAB = "BROWSER_TAB"
    DEVICE_CAMERA = "DEVICE_CAMERA"
    EXTERNAL_IMAGE = "EXTERNAL_IMAGE"
    DOCUMENT_SCAN = "DOCUMENT_SCAN"


class CameraState(StrEnum):
    """Lifecycle state of on-device camera hardware."""

    UNAVAILABLE = "UNAVAILABLE"
    IDLE = "IDLE"
    PERMISSION_REQUIRED = "PERMISSION_REQUIRED"
    ACTIVE_STREAMING = "ACTIVE_STREAMING"
    FRAME_CAPTURED = "FRAME_CAPTURED"
    RELEASED = "RELEASED"


class UIElementType(StrEnum):
    """Taxonomy of detected graphical UI elements."""

    BUTTON = "BUTTON"
    TEXT_FIELD = "TEXT_FIELD"
    CHECKBOX = "CHECKBOX"
    RADIO = "RADIO"
    DROPDOWN = "DROPDOWN"
    DIALOG = "DIALOG"
    LINK = "LINK"
    ICON = "ICON"
    IMAGE = "IMAGE"
    MENU = "MENU"
    TAB = "TAB"
    SLIDER = "SLIDER"
    WARNING = "WARNING"
    NOTIFICATION = "NOTIFICATION"
    UNKNOWN = "UNKNOWN"


class VisualSensitivityType(StrEnum):
    """Privacy classification for sensitive on-screen regions."""

    NONE = "NONE"
    PASSWORD = "PASSWORD"
    API_KEY_OR_SECRET = "API_KEY_OR_SECRET"
    PAYMENT_CARD = "PAYMENT_CARD"
    OTP_OR_PIN = "OTP_OR_PIN"
    PRIVATE_MESSAGE = "PRIVATE_MESSAGE"
    PII = "PII"


# ============================================================================
# 2. Geometry, Grounding & UI Elements
# ============================================================================


class VisualBoundingBox(BaseModel):
    """Normalized [0.0, 1.0] and absolute pixel coordinates."""

    x_min: float = Field(..., ge=0.0, le=1.0, description="Normalized left")
    y_min: float = Field(..., ge=0.0, le=1.0, description="Normalized top")
    x_max: float = Field(..., ge=0.0, le=1.0, description="Normalized right")
    y_max: float = Field(..., ge=0.0, le=1.0, description="Normalized bottom")
    abs_x: int = Field(default=0, ge=0, description="Pixel X coordinate")
    abs_y: int = Field(default=0, ge=0, description="Pixel Y coordinate")
    abs_width: int = Field(default=0, ge=0, description="Pixel width")
    abs_height: int = Field(default=0, ge=0, description="Pixel height")

    def center_point(self) -> tuple[int, int]:
        """Calculates absolute center coordinates (X, Y) for cursor clicking."""
        return (
            self.abs_x + (self.abs_width // 2),
            self.abs_y + (self.abs_height // 2),
        )


class UIElement(BaseModel):
    """Detected interactive or semantic element on screen."""

    element_id: str = Field(default_factory=_gen_id)
    element_type: UIElementType = UIElementType.BUTTON
    label: str = Field(default="", description="Text label or icon semantic name")
    bounding_box: VisualBoundingBox
    is_interactive: bool = True
    is_focused: bool = False
    is_enabled: bool = True
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    value_text: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class VisualRegion(BaseModel):
    """A classified spatial visual region on screen or camera."""

    region_id: str = Field(default_factory=_gen_id)
    label: str
    bounding_box: VisualBoundingBox
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_sensitive: bool = False
    sensitivity_type: VisualSensitivityType = VisualSensitivityType.NONE
    text_content: str | None = None


# ============================================================================
# 3. Multilingual OCR Contracts
# ============================================================================


class OCRWord(BaseModel):
    """An individual recognized word token with bounding geometry."""

    text: str
    bounding_box: VisualBoundingBox
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OCRLine(BaseModel):
    """A horizontal or recognized text line."""

    text: str
    words: list[OCRWord] = Field(default_factory=list)
    bounding_box: VisualBoundingBox
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OCRBlock(BaseModel):
    """A cohesive paragraph or text block."""

    block_id: str = Field(default_factory=_gen_id)
    text: str
    lines: list[OCRLine] = Field(default_factory=list)
    bounding_box: VisualBoundingBox
    language: str = "en"  # en, hi, hinglish, code
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class OCRResult(BaseModel):
    """Comprehensive output of the Multilingual OCR engine."""

    ocr_id: str = Field(default_factory=_gen_id)
    full_text: str
    blocks: list[OCRBlock] = Field(default_factory=list)
    detected_languages: list[str] = Field(default_factory=lambda: ["en"])
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_handwritten: bool = False
    orientation_degrees: float = 0.0
    latency_ms: float = 0.0
    is_untrusted_data: bool = True  # Invariant: OCR is UNTRUSTED data


# ============================================================================
# 4. Multimodal Input Frames & Screen Semantic Models
# ============================================================================


class ImageInput(BaseModel):
    """Arbitrary image provided via file, upload, or clipboard."""

    image_id: str = Field(default_factory=_gen_id)
    source: FrameSource = FrameSource.EXTERNAL_IMAGE
    raw_bytes_base64: str = ""
    mime_type: str = "image/png"
    width: int = Field(default=1920, ge=1)
    height: int = Field(default=1080, ge=1)
    file_path: str | None = None
    sha256_hash: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class CameraFrame(BaseModel):
    """Bounded, user-authorized camera capture frame."""

    frame_id: str = Field(default_factory=_gen_id)
    device_id: str = "pixel-local"
    camera_type: str = "WEBCAM"  # FRONT, BACK, WEBCAM
    raw_bytes_base64: str = ""
    width: int = 1280
    height: int = 720
    timestamp_utc: str = Field(default_factory=_utc_now_iso)
    is_ephemeral: bool = True  # Ephemeral by default: no persistent storage


class ScreenFrame(BaseModel):
    """Screenshot captured from desktop, mobile, or application window."""

    frame_id: str = Field(default_factory=_gen_id)
    device_id: str = "pixel-local"
    source: FrameSource = FrameSource.DESKTOP_SCREEN
    window_title: str | None = None
    app_name: str | None = None
    raw_bytes_base64: str = ""
    width: int = 1920
    height: int = 1080
    timestamp_utc: str = Field(default_factory=_utc_now_iso)
    privacy_classified: bool = False
    has_sensitive_data: bool = False


class DocumentVisualFrame(BaseModel):
    """Visual page frame from a PDF or scanned technical document."""

    document_id: str = Field(default_factory=_gen_id)
    page_number: int = 1
    total_pages: int = 1
    raw_bytes_base64: str = ""
    mime_type: str = "application/pdf"
    width: int = 1600
    height: int = 2200
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class ScreenSemanticModel(BaseModel):
    """Structured semantic representation of an entire visible screen."""

    screen_id: str = Field(default_factory=_gen_id)
    app_name: str = "Unknown"
    window_title: str = ""
    dimensions: tuple[int, int] = (1920, 1080)
    elements: list[UIElement] = Field(default_factory=list)
    dialogs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    active_focused_element_id: str | None = None
    screenshot_hash: str = ""
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 5. Visual Observations, Multimodal Context & Poisoning Defense
# ============================================================================


class VisionObservation(BaseModel):
    """Processed high-level visual observation produced by Vision & OCR engines."""

    observation_id: str = Field(default_factory=_gen_id)
    source_frame_id: str
    source_modality: ModalityType = ModalityType.SCREEN
    summary: str
    detected_entities: list[VisualRegion] = Field(default_factory=list)
    ocr_result: OCRResult | None = None
    screen_model: ScreenSemanticModel | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_untrusted_data: bool = True
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


class MultimodalContextPayload(BaseModel):
    """Unified context payload for the Agent Planner incorporating Vision & Voice."""

    context_id: str = Field(default_factory=_gen_id)
    user_id: str = "default_user"
    session_id: str = "default_session"
    voice_query: str | None = None
    active_screen_summary: str | None = None
    active_camera_summary: str | None = None
    visible_elements_summary: str | None = None
    ocr_extracted_text: str | None = None
    relevant_personal_facts: list[str] = Field(default_factory=list)
    active_goal_title: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_untrusted_visual_data: bool = True
    token_budget_used: int = 0
    assembly_latency_ms: float = 0.0


# ============================================================================
# 6. Visual Action Grounding & Verification Contracts
# ============================================================================


class VisualActionTarget(BaseModel):
    """Resolved visual target coordinates and element reference for an OS action."""

    target_id: str = Field(default_factory=_gen_id)
    element_id: str
    label: str
    element_type: UIElementType
    target_coordinates: tuple[int, int]  # (X, Y) pixel coords
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_ambiguous: bool = False
    candidate_matches_count: int = 1


class VisualVerificationTarget(BaseModel):
    """Specification of expected post-action visual state."""

    expected_element_label: str | None = None
    expected_text_contains: str | None = None
    expected_app_focused: str | None = None
    timeout_ms: float = 2000.0


class VisualVerificationResult(BaseModel):
    """Empirical post-action verification result from before/after screenshot diffing."""

    verification_id: str = Field(default_factory=_gen_id)
    verified: bool
    before_state_hash: str
    after_state_hash: str
    detected_transition: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    explanation: str
    timestamp_utc: str = Field(default_factory=_utc_now_iso)


# ============================================================================
# 7. Visual Memory & Governance Contracts
# ============================================================================


class VisualMemoryCategory(StrEnum):
    """Taxonomy of retained visual knowledge."""

    CURRENT_CONTEXT = "CURRENT_CONTEXT"
    TEMPORARY_CONTEXT = "TEMPORARY_CONTEXT"
    USER_APPROVED_MEMORY = "USER_APPROVED_MEMORY"
    DERIVED_FACT = "DERIVED_FACT"


class VisualMemoryRecord(BaseModel):
    """Durable semantic fact derived from visual perception with full provenance."""

    record_id: str = Field(default_factory=_gen_id)
    user_id: str = "default_user"
    category: VisualMemoryCategory = VisualMemoryCategory.TEMPORARY_CONTEXT
    key: str
    value_summary: str
    source_frame_source: FrameSource = FrameSource.DESKTOP_SCREEN
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    user_confirmed: bool = False
    is_active: bool = True
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime | None = None
    ttl_seconds: int | None = 3600  # Default 1 hour TTL for visual context

    def is_expired(self) -> bool:
        if not self.is_active:
            return True
        if self.expires_at and datetime.now(UTC) > self.expires_at:
            return True
        if self.ttl_seconds is not None:
            age = (datetime.now(UTC) - self.created_at).total_seconds()
            if age >= self.ttl_seconds:
                return True
        return False
