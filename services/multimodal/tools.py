"""PIXEL — Phase 16 Multimodal Capability Tools (L5 Tool Registry).

Provides typed L5 tool implementations for Vision Analysis, OCR Extraction,
Screen Capture, Camera Capture, UI Grounding, Visual Verification, Document Reading,
and Visual Memory Search.
"""

import time
from typing import Any

from packages.contracts.multimodal import (
    DocumentVisualFrame,
    FrameSource,
    ImageInput,
    ScreenFrame,
    VisualVerificationTarget,
)
from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.multimodal.camera_manager import CameraLifecycleManager
from services.multimodal.document_analyzer import DocumentVisualAnalyzer
from services.multimodal.ocr_engine import MultilingualOCREngine
from services.multimodal.providers.router import VisionModelRouter
from services.multimodal.screen_capture_manager import ScreenCaptureManager
from services.multimodal.screen_understanding import ScreenSemanticAnalyzer
from services.multimodal.ui_grounding import UIGroundingEngine
from services.multimodal.visual_injection_defense import VisualInjectionDefense
from services.multimodal.visual_memory_manager import VisualMemoryManager
from services.multimodal.visual_verifier import VisualActionVerifier


class VisionAnalyzeTool(BaseTool):
    """Tool to analyze an image or screen with scene understanding."""

    def __init__(
        self,
        router: VisionModelRouter,
        injection_defense: VisualInjectionDefense | None = None,
    ) -> None:
        self._router = router
        self._injection_defense = injection_defense or VisualInjectionDefense()

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="vision_analyze",
            description="Analyzes an image or screenshot and returns structured visual entities and summary.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "raw_bytes_base64": {"type": "string"},
                    "prompt": {"type": "string"},
                    "width": {"type": "integer", "default": 1920},
                    "height": {"type": "integer", "default": 1080},
                },
                "required": ["raw_bytes_base64"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        img = ImageInput(
            raw_bytes_base64=arguments.get("raw_bytes_base64", ""),
            width=arguments.get("width", 1920),
            height=arguments.get("height", 1080),
        )
        obs = await self._router.analyze_image(img, prompt=arguments.get("prompt"))
        obs = self._injection_defense.sanitize_observation(obs)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=obs.model_dump(),
            duration_ms=duration_ms,
            evidence={"observation_id": obs.observation_id, "confidence": obs.confidence},
        )


class OCRExtractTool(BaseTool):
    """Tool to extract text tokens and geometry from visual media."""

    def __init__(self, ocr_engine: MultilingualOCREngine) -> None:
        self._ocr_engine = ocr_engine

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="ocr_extract",
            description="Extracts multilingual text (English, Hindi, Hinglish, Code) with bounding coordinates.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "text_or_base64": {"type": "string"},
                    "languages": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["text_or_base64"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        ocr_res = await self._ocr_engine.extract_text(
            arguments.get("text_or_base64", ""),
            target_languages=arguments.get("languages"),
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=ocr_res.model_dump(),
            duration_ms=duration_ms,
            evidence={
                "detected_languages": ocr_res.detected_languages,
                "blocks_count": len(ocr_res.blocks),
            },
        )


class CaptureScreenTool(BaseTool):
    """Tool to capture active desktop, mobile, or browser screen with privacy classification."""

    def __init__(self, screen_manager: ScreenCaptureManager) -> None:
        self._screen_manager = screen_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="capture_screen",
            description="Captures bounded screenshot and tags any sensitive visual regions.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "enum": ["DESKTOP_SCREEN", "ANDROID_SCREEN", "BROWSER_TAB"],
                    },
                    "window_title": {"type": "string"},
                },
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        src_str = arguments.get("source", "DESKTOP_SCREEN")
        source = (
            FrameSource(src_str)
            if src_str in FrameSource.__members__
            else FrameSource.DESKTOP_SCREEN
        )
        frame = await self._screen_manager.capture_screen(
            source=source,
            window_title=arguments.get("window_title"),
        )
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=frame.model_dump(),
            duration_ms=duration_ms,
            evidence={"frame_id": frame.frame_id, "has_sensitive_data": frame.has_sensitive_data},
        )


class CaptureCameraFrameTool(BaseTool):
    """Tool to capture ephemeral camera frame with explicit permission governance."""

    def __init__(self, camera_manager: CameraLifecycleManager) -> None:
        self._camera_manager = camera_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="capture_camera_frame",
            description="Captures a single ephemeral camera frame under explicit user authorization.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "camera_type": {"type": "string", "default": "WEBCAM"},
                },
            },
            timeout_ms=5000,
            requires_approval=True,  # Camera requires explicit authorization
            audit_level=AuditLevel.DETAILED,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        try:
            frame = await self._camera_manager.capture_frame(
                camera_type=arguments.get("camera_type", "WEBCAM")
            )
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolExecutionResult(
                success=True,
                output=frame.model_dump(),
                duration_ms=duration_ms,
                evidence={
                    "frame_id": frame.frame_id,
                    "camera_state": self._camera_manager.state.value,
                },
            )
        except PermissionError as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            return ToolExecutionResult(
                success=False,
                error=str(e),
                duration_ms=duration_ms,
            )


class FindVisualElementTool(BaseTool):
    """Tool to locate UI elements on screen without guessing."""

    def __init__(
        self,
        screen_analyzer: ScreenSemanticAnalyzer,
        grounding_engine: UIGroundingEngine,
    ) -> None:
        self._screen_analyzer = screen_analyzer
        self._grounding_engine = grounding_engine

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="find_visual_element",
            description="Locates target UI element coordinates on screen. Rejects ambiguous targets.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "target_query": {"type": "string"},
                    "window_title": {"type": "string"},
                },
                "required": ["target_query"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        dummy_screen = ScreenFrame(window_title=arguments.get("window_title", "Active Desktop"))
        screen_model = await self._screen_analyzer.analyze_screen(dummy_screen)
        target = await self._grounding_engine.ground_target(screen_model, arguments["target_query"])
        duration_ms = int((time.perf_counter() - start) * 1000)

        if not target:
            return ToolExecutionResult(
                success=False,
                error=f"Element matching '{arguments['target_query']}' not found on screen.",
                duration_ms=duration_ms,
            )

        if target.is_ambiguous:
            return ToolExecutionResult(
                success=False,
                error=f"Ambiguous target: {target.candidate_matches_count} matching elements found. Please clarify.",
                output=target.model_dump(),
                duration_ms=duration_ms,
                evidence={"is_ambiguous": True},
            )

        return ToolExecutionResult(
            success=True,
            output=target.model_dump(),
            duration_ms=duration_ms,
            evidence={"coordinates": target.target_coordinates, "confidence": target.confidence},
        )


class CompareVisualStateTool(BaseTool):
    """Tool to verify visual state transition before and after action execution."""

    def __init__(
        self,
        screen_analyzer: ScreenSemanticAnalyzer,
        verifier: VisualActionVerifier,
    ) -> None:
        self._screen_analyzer = screen_analyzer
        self._verifier = verifier

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="compare_visual_state",
            description="Compares before/after UI models to verify expected state transitions.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "before_window_title": {"type": "string"},
                    "after_window_title": {"type": "string"},
                    "expected_element_label": {"type": "string"},
                    "expected_app_focused": {"type": "string"},
                },
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        before_screen = ScreenFrame(window_title=arguments.get("before_window_title", "State A"))
        after_screen = ScreenFrame(window_title=arguments.get("after_window_title", "State B"))

        before_model = await self._screen_analyzer.analyze_screen(before_screen)
        after_model = await self._screen_analyzer.analyze_screen(after_screen)

        target = VisualVerificationTarget(
            expected_element_label=arguments.get("expected_element_label"),
            expected_app_focused=arguments.get("expected_app_focused"),
        )
        res = self._verifier.verify_transition(before_model, after_model, target)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=res.verified,
            output=res.model_dump(),
            duration_ms=duration_ms,
            evidence={"verified": res.verified, "explanation": res.explanation},
        )


class ReadDocumentImageTool(BaseTool):
    """Tool to parse technical documents, tables, and figures visually."""

    def __init__(self, doc_analyzer: DocumentVisualAnalyzer) -> None:
        self._doc_analyzer = doc_analyzer

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="read_document_image",
            description="Extracts structured text, tables, and diagrams from document visual pages.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string"},
                    "raw_bytes_base64": {"type": "string"},
                    "page_number": {"type": "integer", "default": 1},
                },
                "required": ["raw_bytes_base64"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        frame = DocumentVisualFrame(
            document_id=arguments.get("document_id", "doc_01"),
            page_number=arguments.get("page_number", 1),
            raw_bytes_base64=arguments["raw_bytes_base64"],
        )
        res = await self._doc_analyzer.analyze_document(frame)
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=res,
            duration_ms=duration_ms,
            evidence={"document_id": frame.document_id, "page": frame.page_number},
        )


class SearchVisualMemoryTool(BaseTool):
    """Tool to search user-approved visual memory and derived visual facts."""

    def __init__(self, memory_manager: VisualMemoryManager) -> None:
        self._memory_manager = memory_manager

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="search_visual_memory",
            description="Queries stored visual facts, screenshots records, and diagrams with provenance.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                },
                "required": ["query"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start = time.perf_counter()
        records = self._memory_manager.query_visual_memory(arguments["query"])
        duration_ms = int((time.perf_counter() - start) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[r.model_dump() for r in records],
            duration_ms=duration_ms,
            evidence={"results_count": len(records)},
        )
