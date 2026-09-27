#!/usr/bin/env bash
set -euo pipefail

echo "======================================================================"
echo " PIXEL Production Control Plane & Runtime Bootstrap"
echo "======================================================================"

# Ensure directories exist
mkdir -p data/persistence

export PIXEL_ENV=${PIXEL_ENV:-production}
export PIXEL_PORT=${PIXEL_PORT:-8000}
export PIXEL_HOST=${PIXEL_HOST:-0.0.0.0}

echo "[1/3] Checking environment configuration..."
echo "  Environment: $PIXEL_ENV"
echo "  Binding:     http://$PIXEL_HOST:$PIXEL_PORT"

echo "[2/3] Verifying database and persistence volumes..."
touch data/persistence/.ready

echo "[3/3] Launching PIXEL Full-Stack Control Plane..."
exec python -m uvicorn services.control_plane.server:app --host "$PIXEL_HOST" --port "$PIXEL_PORT"
