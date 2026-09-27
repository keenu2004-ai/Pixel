"""PIXEL — Phase 16 Vision Model Router.

Governs dispatching of multimodal processing to LOCAL, REMOTE, or HYBRID providers
respecting privacy classification, latency budgets, and device profiles.
"""

from enum import StrEnum

from packages.contracts.multimodal import (
    CameraFrame,
    ImageInput,
    ScreenFrame,
    VisionObservation,
)
from services.multimodal.providers.base import (
    BaseDocumentVisualProvider,
    BaseOCRProvider,
    BaseUIUnderstandingProvider,
    BaseVisionProvider,
)
from services.multimodal.providers.local_vision import LocalDeterministicVisionProvider


class RoutingStrategy(StrEnum):
    """Execution tier for vision inference."""

    LOCAL = "LOCAL"
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"


class VisionModelRouter:
    """Intelligently routes multimodal tasks to local or remote providers."""

    def __init__(
        self,
        local_provider: BaseVisionProvider | None = None,
        remote_provider: BaseVisionProvider | None = None,
        default_strategy: RoutingStrategy = RoutingStrategy.LOCAL,
    ) -> None:
        self._local_provider = local_provider or LocalDeterministicVisionProvider()
        self._remote_provider = remote_provider
        self._default_strategy = default_strategy

    @property
    def local_provider(self) -> BaseVisionProvider:
        return self._local_provider

    @property
    def ocr_provider(self) -> BaseOCRProvider:
        if isinstance(self._local_provider, BaseOCRProvider):
            return self._local_provider
        raise NotImplementedError("Local provider does not support OCR")

    @property
    def ui_provider(self) -> BaseUIUnderstandingProvider:
        if isinstance(self._local_provider, BaseUIUnderstandingProvider):
            return self._local_provider
        raise NotImplementedError("Local provider does not support UI understanding")

    @property
    def document_provider(self) -> BaseDocumentVisualProvider:
        if isinstance(self._local_provider, BaseDocumentVisualProvider):
            return self._local_provider
        raise NotImplementedError("Local provider does not support Document Visual parsing")

    def determine_strategy(
        self,
        has_sensitive_data: bool = False,
        is_ephemeral_camera: bool = False,
        prefer_remote: bool = False,
    ) -> RoutingStrategy:
        """Determines routing strategy preserving zero-leakage privacy invariants."""
        # Non-negotiable privacy rule: sensitive data or unconsented camera frames NEVER leave local device
        if has_sensitive_data or is_ephemeral_camera:
            return RoutingStrategy.LOCAL

        if prefer_remote and self._remote_provider is not None:
            return RoutingStrategy.REMOTE

        return self._default_strategy

    async def analyze_screen(
        self,
        screen: ScreenFrame,
        prompt: str | None = None,
        force_local: bool = False,
    ) -> VisionObservation:
        """Routes screen analysis safely."""
        strategy = (
            RoutingStrategy.LOCAL
            if force_local
            else self.determine_strategy(has_sensitive_data=screen.has_sensitive_data)
        )

        if strategy == RoutingStrategy.REMOTE and self._remote_provider:
            return await self._remote_provider.analyze_screen(screen, prompt)
        return await self._local_provider.analyze_screen(screen, prompt)

    async def analyze_image(
        self,
        image: ImageInput,
        prompt: str | None = None,
        prefer_remote: bool = False,
    ) -> VisionObservation:
        """Routes image analysis safely."""
        strategy = self.determine_strategy(prefer_remote=prefer_remote)
        if strategy == RoutingStrategy.REMOTE and self._remote_provider:
            return await self._remote_provider.analyze_image(image, prompt)
        return await self._local_provider.analyze_image(image, prompt)

    async def analyze_camera(
        self,
        camera: CameraFrame,
        prompt: str | None = None,
    ) -> VisionObservation:
        """Routes camera frame analysis safely."""
        strategy = self.determine_strategy(is_ephemeral_camera=camera.is_ephemeral)
        if strategy == RoutingStrategy.REMOTE and self._remote_provider:
            return await self._remote_provider.analyze_camera_frame(camera, prompt)
        return await self._local_provider.analyze_camera_frame(camera, prompt)
