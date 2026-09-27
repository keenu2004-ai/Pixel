"""Performance and Latency Benchmark Tests for Phase 10 Control Plane."""

import time

from starlette.testclient import TestClient

from services.control_plane.auth import ControlPlaneAuthManager
from services.control_plane.manager import ControlPlaneManager
from services.control_plane.server import create_control_plane_app


def test_system_overview_latency_benchmark() -> None:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    admin = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None
    token = auth_mgr.create_access_token(admin)
    headers = {"Authorization": f"Bearer {token}"}

    # Warmup
    client.get("/api/v1/overview/system", headers=headers)

    # Benchmark 50 iterations
    latencies: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = client.get("/api/v1/overview/system", headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        latencies.append((t1 - t0) * 1000.0)

    avg_latency = sum(latencies) / len(latencies)
    p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
    print(f"\n[Benchmark] Overview API - Avg: {avg_latency:.2f}ms | P95: {p95_latency:.2f}ms")

    # Target: System overview response < 50ms
    assert avg_latency < 50.0


def test_task_listing_latency_benchmark() -> None:
    auth_mgr = ControlPlaneAuthManager()
    manager = ControlPlaneManager()
    app = create_control_plane_app(manager=manager, auth_manager=auth_mgr)
    client = TestClient(app)

    admin = auth_mgr.authenticate("admin", "pixel-admin-secure-2026")
    assert admin is not None
    token = auth_mgr.create_access_token(admin)
    headers = {"Authorization": f"Bearer {token}"}

    latencies: list[float] = []
    for _ in range(50):
        t0 = time.perf_counter()
        res = client.get("/api/v1/tasks", headers=headers)
        t1 = time.perf_counter()
        assert res.status_code == 200
        latencies.append((t1 - t0) * 1000.0)

    avg_latency = sum(latencies) / len(latencies)
    print(f"\n[Benchmark] Tasks List API - Avg: {avg_latency:.2f}ms")
    assert avg_latency < 30.0
