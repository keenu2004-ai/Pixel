"""
Unit tests for Plugin Subprocess Sandbox Driver.
"""

import os
import tempfile

import pytest

from packages.contracts.ecosystem import (
    PluginExecutionRequest,
    PluginManifest,
    PluginRiskClass,
    PluginRuntimeType,
)
from services.ecosystem.sandbox.subprocess_driver import SubprocessSandboxDriver


@pytest.fixture
def sandbox_driver() -> SubprocessSandboxDriver:
    return SubprocessSandboxDriver()


@pytest.mark.asyncio
async def test_sandbox_executes_valid_plugin(sandbox_driver: SubprocessSandboxDriver) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        entry_code = """
import sys, json

for line in sys.stdin:
    if not line.strip():
        continue
    req = json.loads(line)
    method = req.get("method")
    params = req.get("params", {})
    if method == "add":
        res = params.get("a", 0) + params.get("b", 0)
        print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": res}))
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "error": "unknown method"}))
    sys.stdout.flush()
"""
        with open(os.path.join(tmp_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(entry_code)

        manifest = PluginManifest(
            plugin_id="plugin.calc",
            name="Calculator",
            version="1.0.0",
            publisher="test",
            description="Adds numbers",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="main.py",
            capabilities=[],
            risk_class=PluginRiskClass.LOW,
            integrity_sha256="test",
        )

        request = PluginExecutionRequest(
            plugin_id="plugin.calc",
            action="add",
            parameters={"a": 10, "b": 32},
            timeout_sec=5.0,
        )

        result = await sandbox_driver.execute(
            manifest=manifest,
            plugin_code_dir=tmp_dir,
            request=request,
            granted_capabilities=[],
        )

        assert result.success is True
        assert result.output == 42
        assert result.error is None
        assert result.duration_ms > 0


@pytest.mark.asyncio
async def test_sandbox_enforces_timeout(sandbox_driver: SubprocessSandboxDriver) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        entry_code = """
import time, sys
time.sleep(10)
"""
        with open(os.path.join(tmp_dir, "hang.py"), "w", encoding="utf-8") as f:
            f.write(entry_code)

        manifest = PluginManifest(
            plugin_id="plugin.hang",
            name="Hanging Plugin",
            version="1.0.0",
            publisher="test",
            description="Infinite sleep",
            runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
            entrypoint="hang.py",
            capabilities=[],
            risk_class=PluginRiskClass.HIGH,
            integrity_sha256="test",
        )

        request = PluginExecutionRequest(
            plugin_id="plugin.hang",
            action="run",
            timeout_sec=0.5,
        )

        result = await sandbox_driver.execute(
            manifest=manifest,
            plugin_code_dir=tmp_dir,
            request=request,
            granted_capabilities=[],
        )

        assert result.success is False
        assert result.error is not None
        assert "timed out" in result.error.lower()


@pytest.mark.asyncio
async def test_sandbox_isolates_environment_secrets(
    sandbox_driver: SubprocessSandboxDriver,
) -> None:
    """Ensure host environment variables containing secrets are NOT leaked to the sandbox."""
    os.environ["SECRET_PIXEL_KEY"] = "super_secret_token_12345"
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            entry_code = """
import os, sys, json

for line in sys.stdin:
    req = json.loads(line)
    secret_val = os.environ.get("SECRET_PIXEL_KEY")
    print(json.dumps({"jsonrpc": "2.0", "id": req.get("id"), "result": {"secret_leaked": secret_val}}))
    sys.stdout.flush()
"""
            with open(os.path.join(tmp_dir, "leak_test.py"), "w", encoding="utf-8") as f:
                f.write(entry_code)

            manifest = PluginManifest(
                plugin_id="plugin.leak",
                name="Leak Test",
                version="1.0.0",
                publisher="test",
                description="Checks env",
                runtime=PluginRuntimeType.SUBPROCESS_SANDBOX,
                entrypoint="leak_test.py",
                capabilities=[],
                risk_class=PluginRiskClass.LOW,
                integrity_sha256="test",
            )

            request = PluginExecutionRequest(
                plugin_id="plugin.leak",
                action="check_env",
                timeout_sec=5.0,
            )

            result = await sandbox_driver.execute(
                manifest=manifest,
                plugin_code_dir=tmp_dir,
                request=request,
                granted_capabilities=[],
            )

            assert result.success is True
            assert result.output.get("secret_leaked") is None
    finally:
        os.environ.pop("SECRET_PIXEL_KEY", None)
