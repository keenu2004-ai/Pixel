"""Unit tests for Control Plane WebSocket streaming endpoint."""

import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app


def test_ws_control_plane_unauthenticated() -> None:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/control-plane") as ws:
            ws.receive_text()
            # If server sends error and closes, receiving next raises WebSocketDisconnect
            ws.receive_text()


def test_ws_control_plane_authenticated_stream() -> None:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    admin = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None
    token = auth_mgr.create_access_token(admin)

    with client.websocket_connect(f"/ws/control-plane?token={token}") as ws:
        # First message is CONNECTED welcome
        welcome_raw = ws.receive_text()
        welcome = json.loads(welcome_raw)
        assert welcome["type"] == "CONNECTED"
        assert welcome["user"]["username"] == "admin"

        # Test Ping/Pong
        ws.send_text(json.dumps({"type": "PING"}))
        pong_raw = ws.receive_text()
        pong = json.loads(pong_raw)
        assert pong["type"] == "PONG"
