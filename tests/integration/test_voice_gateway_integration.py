"""Integration tests for Voice Gateway HTTP and WebSocket API."""

from collections.abc import Iterator

import pytest
from starlette.testclient import TestClient

from services.voice_gateway.server import app, health_check


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.asyncio
async def test_gateway_health_endpoint() -> None:
    result = await health_check()
    assert result["status"] == "healthy"
    assert result["service"] == "voice_gateway"
    assert result["version"] == "0.1.0"


def test_gateway_http_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "voice_gateway"


def test_gateway_websocket_connect(client: TestClient) -> None:
    with client.websocket_connect("/ws/voice") as websocket:
        # Send a 100ms dummy PCM audio frame
        dummy_pcm = b"\x00\x00" * 1600
        websocket.send_bytes(dummy_pcm)
        # Send JSON interrupt command
        websocket.send_text('{"action": "interrupt"}')
        received = websocket.receive_text()
        assert "INTERRUPTED" in received or "IDLE" in received or "session_id" in received
