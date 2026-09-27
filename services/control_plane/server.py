"""Unified PIXEL Full-Stack Production Server & Control Plane Gateway."""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from packages.core.config import PixelConfig
from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.routers import (
    audit_router,
    auth_router,
    conversations_router,
    devices_router,
    memory_router,
    overview_router,
    scheduler_router,
    tasks_router,
    ws_router,
)
from services.voice_gateway.server import (
    create_default_pipeline,
    websocket_voice_endpoint,
)

logger = logging.getLogger(__name__)

UI_DIR = os.path.join(os.path.dirname(__file__), "ui")


@asynccontextmanager
async def control_plane_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Lifespan manager for PIXEL Control Plane and Voice Gateway."""
    logger.info("Initializing PIXEL Unified Control Plane & Runtime Services...")
    config = PixelConfig.from_env()
    app.state.config = config

    # Initialize Auth Manager
    auth_manager = ControlPlaneAuthManager(secret_key=config.secret_key)
    app.state.auth_manager = auth_manager

    # Initialize Voice Pipeline
    voice_pipeline = create_default_pipeline()
    app.state.pipeline = voice_pipeline

    # Initialize Control Plane Manager
    control_plane_manager = ControlPlaneManager(voice_pipeline=voice_pipeline)
    app.state.control_plane_manager = control_plane_manager

    yield

    logger.info("Shutting down PIXEL Control Plane...")


def create_control_plane_app(
    config: PixelConfig | None = None,
    manager: ControlPlaneManager | None = None,
    auth_manager: ControlPlaneAuthManager | None = None,
) -> FastAPI:
    """FastAPI Application Factory for the PIXEL Control Plane."""
    app = FastAPI(
        title="PIXEL Full-Stack Control Plane",
        description="Unified operational dashboard, conversation monitoring, task scheduling, memory inspection, and device topology gateway.",
        version="1.0.0",
        lifespan=control_plane_lifespan,
    )

    # 1. CORS Configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob: ws: wss:; "
            "img-src 'self' data: https:; font-src 'self' data: https:; "
            "connect-src 'self' ws: wss: http: https:;"
        )
        return response

    # If instances provided upfront, attach to state
    if auth_manager:
        app.state.auth_manager = auth_manager
    if manager:
        app.state.control_plane_manager = manager

    # 3. Include API Routers
    app.include_router(auth_router)
    app.include_router(overview_router)
    app.include_router(conversations_router)
    app.include_router(tasks_router)
    app.include_router(scheduler_router)
    app.include_router(memory_router)
    app.include_router(devices_router)
    app.include_router(audit_router)
    app.include_router(ws_router)

    # 4. Mount Voice Gateway WebSocket
    app.add_api_websocket_route("/ws/voice", websocket_voice_endpoint)

    # 5. Core Health Check Endpoint
    @app.get("/api/v1/health")
    async def api_health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "version": "1.0.0",
            "service": "pixel_control_plane",
            "environment": os.getenv("PIXEL_ENV", "production"),
        }

    # Backward compatibility with Voice Gateway /health
    @app.get("/health")
    async def legacy_health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "service": "pixel_control_plane",
            "version": "1.0.0",
        }

    # 6. Static UI Assets
    if os.path.exists(UI_DIR):
        app.mount("/static", StaticFiles(directory=UI_DIR), name="static")

        @app.get("/")
        async def serve_ui_root() -> FileResponse:
            index_path = os.path.join(UI_DIR, "index.html")
            return FileResponse(index_path)

    return app


# Default ASGI app instance
app = create_control_plane_app()
