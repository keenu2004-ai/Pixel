"""Voice Gateway WebSocket & HTTP API Server.

Provides /health and /ws/voice WebSocket streaming endpoints for PCM audio streaming.
"""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from packages.contracts.events import AudioFrame, BaseEvent
from services.voice_gateway.pipeline import VoicePipeline
from services.voice_gateway.session import VoiceSession
from services.voice_gateway.stt.whisper_provider import LocalWhisperSTT
from services.voice_gateway.tts.edge_tts_provider import EdgeTTSProvider
from services.voice_gateway.vad.silero_vad import SileroVADProvider
from services.voice_gateway.wake.openwakeword_provider import OpenWakeWordProvider

logger = logging.getLogger(__name__)


def create_default_pipeline() -> VoicePipeline:
    """Instantiates a default VoicePipeline with Silero, OpenWakeWord, Local Whisper, and EdgeTTS."""
    vad = SileroVADProvider()
    wake = OpenWakeWordProvider()
    stt = LocalWhisperSTT()
    tts = EdgeTTSProvider()
    return VoicePipeline(
        vad_provider=vad,
        wake_provider=wake,
        stt_provider=stt,
        tts_provider=tts,
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """FastAPI application lifespan setup and teardown."""
    logger.info("Initializing PIXEL Voice Gateway...")
    if not hasattr(app.state, "pipeline"):
        app.state.pipeline = create_default_pipeline()
    yield
    logger.info("Shutting down PIXEL Voice Gateway.")


app = FastAPI(
    title="PIXEL Voice Gateway",
    description="Real-time voice streaming gateway with VAD, Wake Word, STT, TTS, and barge-in.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, Any]:
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "voice_gateway",
        "version": "0.1.0",
    }


@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket) -> None:
    """Real-time bidirectional WebSocket endpoint for streaming PCM audio and voice events."""
    await websocket.accept()
    session_id = f"sess_{websocket.client.port if websocket.client else 'client'}"
    session = VoiceSession(session_id=session_id)

    pipeline: VoicePipeline
    if hasattr(websocket.app.state, "pipeline"):
        pipeline = websocket.app.state.pipeline
    else:
        pipeline = create_default_pipeline()
        websocket.app.state.pipeline = pipeline

    logger.info("WebSocket connected for session: %s", session_id)
    timestamp_ms = 0

    try:
        while True:
            message = await websocket.receive()
            if "bytes" in message and message["bytes"]:
                raw_bytes: bytes = message["bytes"]
                frame = AudioFrame(
                    sample_rate=16000,
                    channels=1,
                    pcm_data=raw_bytes,
                    timestamp_ms=timestamp_ms,
                )
                timestamp_ms += int(len(raw_bytes) / (16000 * 2) * 1000)

                async for output in pipeline.process_frame(frame, session):
                    if isinstance(output, BaseEvent):
                        await websocket.send_text(output.model_dump_json())
                    elif isinstance(output, bytes):
                        await websocket.send_bytes(output)

            elif "text" in message and message["text"]:
                try:
                    cmd_data = json.loads(message["text"])
                    if cmd_data.get("action") == "interrupt":
                        session.cancel_active_playback()
                        evt = session.transition_to(
                            session.state, reason="Client explicitly sent interrupt signal"
                        )
                        await websocket.send_text(evt.model_dump_json())
                except Exception as parse_err:
                    logger.warning("Failed to parse client JSON message: %s", parse_err)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for session: %s", session_id)
    except Exception as err:
        logger.error("Error in WebSocket session [%s]: %s", session_id, err)
        try:
            await websocket.close()
        except Exception:
            pass
