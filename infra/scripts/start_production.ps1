# PIXEL Production Control Plane Windows Bootstrap
$ErrorActionPreference = "Stop"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host " PIXEL Production Control Plane & Runtime Bootstrap (Windows)" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

if (-not (Test-Path -Path "data\persistence")) {
    New-Item -ItemType Directory -Path "data\persistence" -Force | Out-Null
}

$env:PIXEL_ENV = if ($env:PIXEL_ENV) { $env:PIXEL_ENV } else { "production" }
$env:PIXEL_PORT = if ($env:PIXEL_PORT) { $env:PIXEL_PORT } else { "8000" }
$env:PIXEL_HOST = if ($env:PIXEL_HOST) { $env:PIXEL_HOST } else { "127.0.0.1" }

Write-Host "[1/3] Environment: $env:PIXEL_ENV" -ForegroundColor Green
Write-Host "[2/3] Endpoint:    http://$env:PIXEL_HOST:$env:PIXEL_PORT" -ForegroundColor Green
Write-Host "[3/3] Starting Uvicorn ASGI Server..." -ForegroundColor Green

python -m uvicorn services.control_plane.server:app --host $env:PIXEL_HOST --port $env:PIXEL_PORT
