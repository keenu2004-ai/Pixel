# ==============================================================================
# PIXEL Full-Stack Production Container (Multi-Stage Build)
# ==============================================================================

# Stage 1: Build & Dependency Resolution
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies into virtualenv
COPY pyproject.toml ./
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel && \
    /opt/venv/bin/pip install --no-cache-dir \
    fastapi \
    uvicorn \
    pydantic \
    starlette \
    websockets \
    numpy \
    pytest \
    pytest-asyncio \
    ruff \
    mypy \
    requests

# Stage 2: Minimal Production Runtime
FROM python:3.12-slim AS runtime

LABEL maintainer="PIXEL Core Engineering Team <core@pixel.ai>"
LABEL version="1.0.0"
LABEL description="PIXEL Voice Gateway, Agent Runtime & Production Control Plane"

WORKDIR /app

# Install runtime OS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIXEL_ENV=production
ENV PIXEL_PORT=8000
ENV PIXEL_HOST=0.0.0.0

# Create non-root application user and persistent data directories
RUN groupadd -g 1001 pixelgroup && \
    useradd -u 1001 -g pixelgroup -s /bin/bash -m pixeluser && \
    mkdir -p /app/data/persistence && \
    chown -R pixeluser:pixelgroup /app

# Copy application source code
COPY --chown=pixeluser:pixelgroup packages /app/packages
COPY --chown=pixeluser:pixelgroup services /app/services
COPY --chown=pixeluser:pixelgroup pyproject.toml /app/pyproject.toml

USER pixeluser

# Expose HTTP / WebSocket Control Plane port
EXPOSE 8000

# Health check probe against API health endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Graceful termination signal
STOPSIGNAL SIGTERM

# Production entrypoint running Uvicorn ASGI server
CMD ["python", "-m", "uvicorn", "services.control_plane.server:app", "--host", "0.0.0.0", "--port", "8000"]
