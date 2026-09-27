"""PIXEL — Phase 16 Multimodal Perception Manager Facade.

Integrates Vision, Multilingual OCR, Screen Understanding, UI Grounding, Camera Lifecycle,
Sensitive Region Protection, Visual Prompt-Injection Defense, Visual Action Verification,
and Multimodal Context Fusion into a unified high-performance facade.
"""

from typing import Any

from packages.contracts.multimodal import (
    FrameSource,
    MultimodalContextPayload,
    ScreenFrame,
    ScreenSemanticModel,
    VisualActionTarget,
    VisualVerificationResult,
    VisualVerificationTarget,
)
from packages.contracts.personalization import AssembledPersonalContext
from services.multimodal.camera_manager import CameraLifecycleManager
from services.multimodal.document_analyzer import DocumentVisualAnalyzer
from services.multimodal.multimodal_context_engine import MultimodalContextEngine
from services.multimodal.ocr_engine import MultilingualOCREngine
from services.multimodal.providers.local_vision import LocalDeterministicVisionProvider
from services.multimodal.providers.router import VisionModelRouter
from services.multimodal.resource_governor import VisionResourceGovernor
from services.multimodal.screen_capture_manager import ScreenCaptureManager
from services.multimodal.screen_understanding import ScreenSemanticAnalyzer
from services.multimodal.sensitive_screen_detector import SensitiveScreenDetector
from services.multimodal.tools import (
    CaptureCameraFrameTool,
    CaptureScreenTool,
    CompareVisualStateTool,
    FindVisualElementTool,
    OCRExtractTool,
    ReadDocumentImageTool,
    SearchVisualMemoryTool,
    VisionAnalyzeTool,
)
from services.multimodal.ui_grounding import UIGroundingEngine
from services.multimodal.visual_injection_defense import VisualInjectionDefense
from services.multimodal.visual_memory_manager import VisualMemoryManager
from services.multimodal.visual_verifier import VisualActionVerifier


class MultimodalPerceptionManager:
    """Master manager for all Phase 16 multimodal perceptual capabilities."""

    def __init__(
        self,
        device_id: str = "pixel-local",
        user_id: str = "default_user",
    ) -> None:
        self._device_id = device_id
        self._user_id = user_id

        # 1. Base Providers & Model Router
        self._local_provider = LocalDeterministicVisionProvider()
        self._router = VisionModelRouter(local_provider=self._local_provider)

        # 2. Perceptual Engines
        self._ocr_engine = MultilingualOCREngine(provider=self._local_provider)
        self._screen_analyzer = ScreenSemanticAnalyzer(provider=self._local_provider)
        self._ui_grounding = UIGroundingEngine(provider=self._local_provider)
        self._sensitive_detector = SensitiveScreenDetector()
        self._injection_defense = VisualInjectionDefense()

        # 3. Hardware / Device Managers
        self._camera_manager = CameraLifecycleManager(device_id=device_id)
        self._screen_manager = ScreenCaptureManager(
            device_id=device_id,
            sensitive_detector=self._sensitive_detector,
        )
        self._doc_analyzer = DocumentVisualAnalyzer(
            ocr_engine=self._ocr_engine,
            provider=self._local_provider,
        )

        # 4. Memory, Verification & Governance
        self._visual_memory = VisualMemoryManager(user_id=user_id)
        self._visual_verifier = VisualActionVerifier()
        self._resource_governor = VisionResourceGovernor()
        self._context_engine = MultimodalContextEngine()

        # 5. Tools
        self._tools = [
            VisionAnalyzeTool(self._router, self._injection_defense),
            OCRExtractTool(self._ocr_engine),
            CaptureScreenTool(self._screen_manager),
            CaptureCameraFrameTool(self._camera_manager),
            FindVisualElementTool(self._screen_analyzer, self._ui_grounding),
            CompareVisualStateTool(self._screen_analyzer, self._visual_verifier),
            ReadDocumentImageTool(self._doc_analyzer),
            SearchVisualMemoryTool(self._visual_memory),
        ]

    # --- Property Accessors ---
    @property
    def router(self) -> VisionModelRouter:
        return self._router

    @property
    def ocr_engine(self) -> MultilingualOCREngine:
        return self._ocr_engine

    @property
    def screen_analyzer(self) -> ScreenSemanticAnalyzer:
        return self._screen_analyzer

    @property
    def ui_grounding(self) -> UIGroundingEngine:
        return self._ui_grounding

    @property
    def sensitive_detector(self) -> SensitiveScreenDetector:
        return self._sensitive_detector

    @property
    def injection_defense(self) -> VisualInjectionDefense:
        return self._injection_defense

    @property
    def camera_manager(self) -> CameraLifecycleManager:
        return self._camera_manager

    @property
    def screen_manager(self) -> ScreenCaptureManager:
        return self._screen_manager

    @property
    def doc_analyzer(self) -> DocumentVisualAnalyzer:
        return self._doc_analyzer

    @property
    def visual_memory(self) -> VisualMemoryManager:
        return self._visual_memory

    @property
    def visual_verifier(self) -> VisualActionVerifier:
        return self._visual_verifier

    @property
    def resource_governor(self) -> VisionResourceGovernor:
        return self._resource_governor

    @property
    def context_engine(self) -> MultimodalContextEngine:
        return self._context_engine

    @property
    def tools(self) -> list[Any]:
        return self._tools

    # --- High-Level Operations ---
    async def process_screen_query(
        self,
        query: str,
        window_title: str | None = None,
        source: FrameSource = FrameSource.DESKTOP_SCREEN,
        personal_context: AssembledPersonalContext | None = None,
    ) -> MultimodalContextPayload:
        """Captures screen, extracts semantics, classifies privacy, and fuses context."""
        screen_frame = await self._screen_manager.capture_screen(
            source=source, window_title=window_title
        )
        observation = await self._router.analyze_screen(screen_frame, prompt=query)
        observation = self._injection_defense.sanitize_observation(observation)

        return self._context_engine.assemble_context(
            voice_query=query,
            screen_observation=observation,
            personal_context=personal_context,
            user_id=self._user_id,
        )

    async def execute_grounded_click(
        self,
        user_intent: str,
        screen_frame: ScreenFrame | None = None,
    ) -> tuple[VisualActionTarget | None, str]:
        """Locates click target with strict ambiguity defense."""
        if not screen_frame:
            screen_frame = await self._screen_manager.capture_screen()

        screen_model = await self._screen_analyzer.analyze_screen(screen_frame)
        target = await self._ui_grounding.ground_target(screen_model, user_intent)

        if not target:
            return None, f"Could not find any UI element matching '{user_intent}'."

        if target.is_ambiguous:
            return (
                target,
                f"Ambiguous target: {target.candidate_matches_count} matching elements found. Please clarify.",
            )

        return (
            target,
            f"Target grounded at coordinates ({target.target_coordinates[0]}, {target.target_coordinates[1]}).",
        )

    def verify_action_result(
        self,
        before_model: ScreenSemanticModel,
        after_model: ScreenSemanticModel,
        target: VisualVerificationTarget,
    ) -> VisualVerificationResult:
        """Performs empirical verification of UI state transition."""
        return self._visual_verifier.verify_transition(before_model, after_model, target)
