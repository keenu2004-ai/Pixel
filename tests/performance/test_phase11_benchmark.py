"""
Performance & Latency Benchmark Suite for Phase 11 Ecosystem & Extensibility Hub.
"""

import os
import tempfile
import time

import pytest

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    BackupScope,
    CommunitySkillManifest,
    ConnectorConfig,
    ConnectorType,
    PluginCapability,
    PluginExecutionRequest,
    PluginManifest,
    PluginRuntimeType,
)
from services.ecosystem.backup.crypto import BackupCryptoEngine
from services.ecosystem.connectors.slack import SlackConnector
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver
from services.ecosystem.vetting import SkillVettingPipeline


@pytest.mark.asyncio
async def test_benchmark_sandbox_execution_latency() -> None:
    """Benchmark sandboxed subprocess execution duration."""
    driver = SubprocessSandboxDriver()
    with tempfile.TemporaryDirectory() as tmp_dir:
        entry_code = """
import sys, json
for line in sys.stdin:
    req = json.loads(line)
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": "ok"}))
    sys.stdout.flush()
"""
        with open(os.path.join(tmp_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(entry_code)

        manifest = PluginManifest(
            plugin_id="plugin.bench",
            name="Bench",
            version="1.0.0",
            publisher="bench",
            description="bench",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="main.py",
            capabilities=[],
            integrity_sha256="test",
        )
        req = PluginExecutionRequest(plugin_id="plugin.bench", action="ping")

        # Warm up
        await driver.execute(manifest, tmp_dir, req, [])

        # Measure
        durations = []
        for _ in range(5):
            t0 = time.perf_counter()
            res = await driver.execute(manifest, tmp_dir, req, [])
            t1 = time.perf_counter()
            assert res.success is True
            durations.append((t1 - t0) * 1000)

        avg_latency = sum(durations) / len(durations)
        print(f"\n[BENCHMARK] Sandboxed Subprocess Avg Latency: {avg_latency:.2f}ms")
        # Subprocess spawn overhead in Python on Windows is typically 30-80ms
        assert avg_latency < 250.0  # Safe threshold


def test_benchmark_ast_security_vetting_speed() -> None:
    """Benchmark AST scanner throughput across multiple source files."""
    pipeline = SkillVettingPipeline()
    manifest = CommunitySkillManifest(
        skill_id="skill.bench",
        publisher="bench",
        version="1.0.0",
        display_name="Bench Skill",
        description="Bench",
        capabilities=[PluginCapability.TOOL_INVOCATION],
    )
    code = """
import sys, json, math

def calculate(a, b):
    return math.sqrt(a**2 + b**2)

for line in sys.stdin:
    req = json.loads(line)
    p = req.get("params", {})
    res = calculate(p.get("a", 3), p.get("b", 4))
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": res}))
    sys.stdout.flush()
"""
    files = {"main.py": code, "helper.py": "def helper(): return True"}

    durations = []
    for _ in range(20):
        t0 = time.perf_counter()
        report = pipeline.vet_skill(manifest, files)
        t1 = time.perf_counter()
        assert report.passed is True
        durations.append((t1 - t0) * 1000)

    avg_latency = sum(durations) / len(durations)
    print(f"\n[BENCHMARK] AST Security Vetting Avg Latency: {avg_latency:.3f}ms")
    assert avg_latency < 10.0  # Target < 10ms


def test_benchmark_backup_encryption_and_decryption() -> None:
    """Benchmark client-side AES-256-GCM encryption & decryption throughput."""
    payload = (
        b'{"facts": [{"id": 1, "text": "fact_01"}, {"id": 2, "text": "fact_02"}], "devices": []}'
    )
    passphrase = "master_benchmark_passphrase_2026"

    # Pre-derive key or benchmark full cycle with KDF
    t0 = time.perf_counter()
    envelope = BackupCryptoEngine.encrypt_payload(
        payload_bytes=payload,
        passphrase=passphrase,
        user_id="user_admin",
        device_id="dev_01",
        scope=BackupScope.ALL,
    )
    encrypt_latency = (time.perf_counter() - t0) * 1000

    t1 = time.perf_counter()
    decrypted = BackupCryptoEngine.decrypt_payload(envelope, passphrase)
    decrypt_latency = (time.perf_counter() - t1) * 1000

    assert decrypted == payload
    print(f"\n[BENCHMARK] Backup Full Encrypt (with PBKDF2 100k): {encrypt_latency:.2f}ms")
    print(f"[BENCHMARK] Backup Full Decrypt (with PBKDF2 100k): {decrypt_latency:.2f}ms")
    assert encrypt_latency < 300.0
    assert decrypt_latency < 300.0


@pytest.mark.asyncio
async def test_benchmark_webhook_delivery_dispatch() -> None:
    """Benchmark outbound webhook connector formatting and delivery latency."""
    cfg = ConnectorConfig(
        connector_id="conn_bench",
        name="Bench Slack",
        connector_type=ConnectorType.SLACK,
        target_url="https://hooks.slack.com/services/bench",
    )
    connector = SlackConnector(cfg)
    event = AutonomousEvent(
        event_id="evt_bench_1",
        correlation_id="corr_bench_1",
        event_type="TASK_PROGRESS",
        source="benchmark",
        payload={"step": 5, "total": 10},
    )

    t0 = time.perf_counter()
    record = await connector.deliver(event)
    dispatch_latency = (time.perf_counter() - t0) * 1000

    assert record.success is True
    print(f"\n[BENCHMARK] Webhook Dispatch Latency: {dispatch_latency:.2f}ms")
    assert dispatch_latency < 100.0
