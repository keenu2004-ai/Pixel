"""Real-time WebSocket streaming router for PIXEL Control Plane."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from packages.contracts.control_plane import ControlPlaneStreamEvent
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws/control-plane")
async def websocket_control_plane(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """Real-time bidirectional event stream for the Control Plane UI."""
    await websocket.accept()

    # 1. Auth Validation
    auth_manager: ControlPlaneAuthManager
    if hasattr(websocket.app.state, "auth_manager"):
        auth_manager = websocket.app.state.auth_manager
    else:
        auth_manager = ControlPlaneAuthManager()
        websocket.app.state.auth_manager = auth_manager

    manager: ControlPlaneManager
    if hasattr(websocket.app.state, "control_plane_manager"):
        manager = websocket.app.state.control_plane_manager
    else:
        manager = ControlPlaneManager()
        websocket.app.state.control_plane_manager = manager

    # Check token from query parameter or require auth message
    authenticated_user = None
    if token:
        token_payload = auth_manager.verify_token(token)
        if token_payload:
            authenticated_user = auth_manager.get_user_by_id(token_payload.sub)

    if not authenticated_user:
        # Give client one chance to send auth JSON frame: {"type": "AUTH", "token": "..."}
        try:
            raw_init = await asyncio.wait_for(websocket.receive_text(), timeout=5.0)
            init_msg = json.loads(raw_init)
            if init_msg.get("type") == "AUTH" and "token" in init_msg:
                t_payload = auth_manager.verify_token(init_msg["token"])
                if t_payload:
                    authenticated_user = auth_manager.get_user_by_id(t_payload.sub)
        except Exception:
            pass

    if not authenticated_user:
        logger.warning("Unauthenticated WebSocket connection rejected on /ws/control-plane")
        await websocket.send_text(
            json.dumps({"type": "ERROR", "message": "Authentication required"})
        )
        await websocket.close(code=1008)
        return

    logger.info(
        "Control Plane WebSocket authenticated for user '%s' (%s)",
        authenticated_user.username,
        authenticated_user.role.value,
    )

    # Subscribe to real-time events
    event_queue = manager.subscribe_events()

    # Send initial welcome and state snapshot
    await websocket.send_text(
        json.dumps(
            {
                "type": "CONNECTED",
                "user": authenticated_user.model_dump(mode="json"),
                "message": "Connected to PIXEL Control Plane Event Stream",
            }
        )
    )

    async def forward_events() -> None:
        """Forward broadcast events from queue to WebSocket."""
        while True:
            evt: ControlPlaneStreamEvent = await event_queue.get()
            await websocket.send_text(evt.model_dump_json())

    async def receive_client_commands() -> None:
        """Receive ping/pong or client action requests."""
        while True:
            msg_text = await websocket.receive_text()
            try:
                msg = json.loads(msg_text)
                if msg.get("type") == "PING":
                    await websocket.send_text(json.dumps({"type": "PONG"}))
            except Exception:
                pass

    forward_task = asyncio.create_task(forward_events())
    receive_task = asyncio.create_task(receive_client_commands())

    try:
        done, pending = await asyncio.wait(
            [forward_task, receive_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for t in pending:
            t.cancel()
    except WebSocketDisconnect:
        logger.info("Control Plane WebSocket disconnected for '%s'", authenticated_user.username)
    except Exception as err:
        logger.error("Control Plane WebSocket error: %s", err)
    finally:
        forward_task.cancel()
        receive_task.cancel()
        manager.unsubscribe_events(event_queue)
        try:
            await websocket.close()
        except Exception:
            pass
