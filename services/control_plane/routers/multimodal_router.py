"""PIXEL — Control Plane Multimodal Perception & Vision Router.

Exposes REST APIs for:
1. Multilingual OCR Text Extraction
2. Screen Understanding & Privacy Detection
3. UI Target Grounding (Zero-Guessing)
4. Visual State Verification
5. Ephemeral Camera Capture Lifecycle
6. Visual Memory Search & Right-to-Forget Purging
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from packages.contracts.control_plane import UserIdentity, UserRole
from packages.contracts.multimodal import (
    FrameSource,
    OCRResult,
    ScreenFrame,
    UIElementType,
    VisionObservation,
    VisualActionTarget,
    VisualVerificationResult,
    VisualVerificationTarget,
)
from services.control_plane.dependencies import (
    get_control_plane_manager,
    require_role,
)
from services.control_plane.manager import ControlPlaneManager
from services.multimodal.manager import MultimodalPerceptionManager

router = APIRouter(prefix="/api/v1/multimodal", tags=["Multimodal Perception & Vision"])


class OCRRequest(BaseModel):
    text_or_base64: str
    languages: list[str] = ["en"]
    orientation_degrees: float = 0.0


class ScreenAnalysisRequest(BaseModel):
    window_title: str | None = None
    app_name: str | None = None
    source: FrameSource = FrameSource.DESKTOP_SCREEN
    prompt: str | None = None


class UIGroundRequest(BaseModel):
    target_query: str
    window_title: str | None = None
    element_type: UIElementType | None = None


class VisualVerifyRequest(BaseModel):
    before_window_title: str
    after_window_title: str
    expected_element_label: str | None = None
    expected_app_focused: str | None = None
    expected_text_contains: str | None = None


class CameraCaptureRequest(BaseModel):
    camera_type: str = "WEBCAM"
    width: int = 1280
    height: int = 720


class VisualMemorySearchRequest(BaseModel):
    query: str
    user_id: str = "default_user"


class VisualMemoryPurgeRequest(BaseModel):
    query_or_key: str | None = None
    purge_all: bool = False
    user_id: str = "default_user"


def _get_multimodal_manager(manager: ControlPlaneManager) -> MultimodalPerceptionManager:
    if hasattr(manager, "multimodal_manager") and manager.multimodal_manager:
        return manager.multimodal_manager
    return MultimodalPerceptionManager()


@router.post("/ocr", response_model=OCRResult)
async def extract_ocr(
    req: OCRRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> OCRResult:
    """Runs multilingual OCR extraction tagging result as untrusted data."""
    mm = _get_multimodal_manager(manager)
    return await mm.ocr_engine.extract_text(
        req.text_or_base64,
        target_languages=req.languages,
        orientation_degrees=req.orientation_degrees,
    )


@router.post("/screen/analyze", response_model=VisionObservation)
async def analyze_screen(
    req: ScreenAnalysisRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> VisionObservation:
    """Captures and analyzes screen, classifying privacy and defending against injections."""
    mm = _get_multimodal_manager(manager)
    screen_frame = await mm.screen_manager.capture_screen(
        source=req.source,
        window_title=req.window_title,
        app_name=req.app_name,
    )
    obs = await mm.router.analyze_screen(screen_frame, prompt=req.prompt)
    return mm.injection_defense.sanitize_observation(obs)


@router.post("/ground", response_model=VisualActionTarget)
async def ground_ui_target(
    req: UIGroundRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> VisualActionTarget:
    """Grounds user intent to exact on-screen UI target coordinates without guessing."""
    mm = _get_multimodal_manager(manager)
    screen_frame = await mm.screen_manager.capture_screen(window_title=req.window_title)
    screen_model = await mm.screen_analyzer.analyze_screen(screen_frame)
    target = await mm.ui_grounding.ground_target(
        screen_model,
        req.target_query,
        element_type_filter=req.element_type,
    )
    if not target:
        raise HTTPException(
            status_code=404,
            detail=f"Target '{req.target_query}' not found on screen.",
        )
    return target


@router.post("/verify", response_model=VisualVerificationResult)
async def verify_visual_state(
    req: VisualVerifyRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.OPERATOR))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> VisualVerificationResult:
    """Empirically verifies UI state transition before and after action."""
    mm = _get_multimodal_manager(manager)
    before_frame = ScreenFrame(window_title=req.before_window_title)
    after_frame = ScreenFrame(window_title=req.after_window_title)

    before_model = await mm.screen_analyzer.analyze_screen(before_frame)
    after_model = await mm.screen_analyzer.analyze_screen(after_frame)

    target = VisualVerificationTarget(
        expected_element_label=req.expected_element_label,
        expected_app_focused=req.expected_app_focused,
        expected_text_contains=req.expected_text_contains,
    )
    return mm.verify_action_result(before_model, after_model, target)


@router.post("/camera/capture")
async def capture_camera_frame(
    req: CameraCaptureRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Captures bounded ephemeral camera frame under explicit authorization."""
    mm = _get_multimodal_manager(manager)
    try:
        frame = await mm.camera_manager.capture_frame(
            camera_type=req.camera_type,
            width=req.width,
            height=req.height,
        )
        return {"success": True, "frame": frame.model_dump()}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e


@router.post("/memory/search")
async def search_visual_memory(
    req: VisualMemorySearchRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.READ_ONLY))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Queries active user-approved visual memory records."""
    mm = _get_multimodal_manager(manager)
    records = mm.visual_memory.query_visual_memory(req.query)
    return {"results": [r.model_dump() for r in records], "count": len(records)}


@router.delete("/memory")
async def purge_visual_memory(
    req: VisualMemoryPurgeRequest,
    user: Annotated[UserIdentity, Depends(require_role(UserRole.ADMIN))],
    manager: Annotated[ControlPlaneManager, Depends(get_control_plane_manager)],
) -> dict[str, Any]:
    """Executes right-to-forget visual memory deletion."""
    mm = _get_multimodal_manager(manager)
    if req.purge_all:
        deleted = mm.visual_memory.delete_all_visual_memories()
    elif req.query_or_key:
        deleted = mm.visual_memory.delete_by_query_or_key(req.query_or_key)
    else:
        deleted = mm.visual_memory.purge_expired()

    return {"success": True, "deleted_count": deleted}
