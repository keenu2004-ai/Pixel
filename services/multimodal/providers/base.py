"""PIXEL — Phase 16 Multimodal Perception Provider Interfaces.

Defines vendor-independent abstractions for Vision, OCR, UI Understanding,
and Document visual parsing.
"""

from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.multimodal import (
    CameraFrame,
    DocumentVisualFrame,
    ImageInput,
    OCRResult,
    ScreenFrame,
    ScreenSemanticModel,
    VisionObservation,
    VisualActionTarget,
)


class BaseVisionProvider(ABC):
    """Abstract interface for high-level image and scene understanding."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the vision provider."""
        ...

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """Whether this provider executes strictly on-device."""
        ...

    @abstractmethod
    async def analyze_image(
        self,
        image: ImageInput,
        prompt: str | None = None,
    ) -> VisionObservation:
        """Analyzes an arbitrary image input and returns structured observation."""
        ...

    @abstractmethod
    async def analyze_screen(
        self,
        screen: ScreenFrame,
        prompt: str | None = None,
    ) -> VisionObservation:
        """Analyzes an active desktop/mobile screenshot."""
        ...

    @abstractmethod
    async def analyze_camera_frame(
        self,
        camera: CameraFrame,
        prompt: str | None = None,
    ) -> VisionObservation:
        """Analyzes a camera frame captured from local or paired hardware."""
        ...


class BaseOCRProvider(ABC):
    """Abstract interface for multilingual optical character recognition."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the OCR provider."""
        ...

    @abstractmethod
    async def extract_text(
        self,
        image_bytes_base64: str,
        languages: list[str] | None = None,
    ) -> OCRResult:
        """Extracts structured text lines, words, geometry, and detected language."""
        ...


class BaseUIUnderstandingProvider(ABC):
    """Abstract interface for screen hierarchy and UI element detection."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the UI understanding provider."""
        ...

    @abstractmethod
    async def parse_screen_model(
        self,
        screen: ScreenFrame,
    ) -> ScreenSemanticModel:
        """Extracts interactive UI elements, dialogs, warnings, and hierarchy."""
        ...

    @abstractmethod
    async def ground_element(
        self,
        screen_model: ScreenSemanticModel,
        target_description: str,
        element_type_filter: str | None = None,
    ) -> VisualActionTarget | None:
        """Locates the exact target element or returns None if ambiguous/not found."""
        ...


class BaseDocumentVisualProvider(ABC):
    """Abstract interface for visual parsing of technical documents/PDFs."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier of the document provider."""
        ...

    @abstractmethod
    async def analyze_document_page(
        self,
        document_frame: DocumentVisualFrame,
    ) -> dict[str, Any]:
        """Analyzes tables, diagrams, and text structure from a document page."""
        ...
