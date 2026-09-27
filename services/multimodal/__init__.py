"""PIXEL — Phase 16 Multimodal Perception, Vision & World Understanding Package.

Exports core engines, providers, managers, and tool registry items.
"""

from services.multimodal.camera_manager import CameraLifecycleManager
from services.multimodal.document_analyzer import DocumentVisualAnalyzer
from services.multimodal.manager import MultimodalPerceptionManager
from services.multimodal.multimodal_context_engine import MultimodalContextEngine
from services.multimodal.ocr_engine import MultilingualOCREngine
from services.multimodal.providers.base import (
    BaseDocumentVisualProvider,
    BaseOCRProvider,
    BaseUIUnderstandingProvider,
    BaseVisionProvider,
)
from services.multimodal.providers.local_vision import LocalDeterministicVisionProvider
from services.multimodal.providers.router import RoutingStrategy, VisionModelRouter
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

__all__ = [
    "BaseVisionProvider",
    "BaseOCRProvider",
    "BaseUIUnderstandingProvider",
    "BaseDocumentVisualProvider",
    "LocalDeterministicVisionProvider",
    "VisionModelRouter",
    "RoutingStrategy",
    "MultilingualOCREngine",
    "ScreenSemanticAnalyzer",
    "UIGroundingEngine",
    "SensitiveScreenDetector",
    "VisualInjectionDefense",
    "CameraLifecycleManager",
    "ScreenCaptureManager",
    "DocumentVisualAnalyzer",
    "VisualMemoryManager",
    "VisualActionVerifier",
    "VisionResourceGovernor",
    "MultimodalContextEngine",
    "MultimodalPerceptionManager",
    "VisionAnalyzeTool",
    "OCRExtractTool",
    "CaptureScreenTool",
    "CaptureCameraFrameTool",
    "FindVisualElementTool",
    "CompareVisualStateTool",
    "ReadDocumentImageTool",
    "SearchVisualMemoryTool",
]
