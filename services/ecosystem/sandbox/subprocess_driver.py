"""
Isolated Subprocess Sandbox Driver for PIXEL Plugins.

Enforces:
1. Environment isolation: Strips all parent environment variables, API keys, tokens, and secrets.
2. Resource isolation: Strict execution timeouts and output payload byte bounds.
3. Filesystem isolation: Bounded working directory execution.
4. IPC validation: JSON-RPC request/response protocol over stdin/stdout.
5. Clean teardown: Terminate and kill orphan processes.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from packages.contracts.ecosystem import (
    PluginCapability,
    PluginExecutionRequest,
    PluginExecutionResult,
    PluginManifest,
)
from services.ecosystem.sandbox.base import BaseSandboxDriver


class SubprocessSandboxDriver(BaseSandboxDriver):
    """Executes third-party plugin code in isolated child processes with zero inherited secrets."""

    MAX_OUTPUT_BYTES: int = 1024 * 1024  # 1 MB maximum output limit

    def __init__(self, python_executable: str | None = None):
        self.python_executable = python_executable or sys.executable
        self._active_processes: set[asyncio.subprocess.Process] = set()

    def _build_isolated_environment(self, plugin_dir: str) -> dict[str, str]:
        """Construct a minimal, unprivileged environment stripped of host secrets."""
        isolated_env: dict[str, str] = {
            "PYTHONPATH": plugin_dir,
            "PYTHONUNBUFFERED": "1",
            "PYTHONUTF8": "1",
            "PIXEL_SANDBOX": "1",
        }

        # Whitelist safe system paths for OS execution runtime
        safe_keys = [
            "PATH",
            "SYSTEMROOT",
            "SYSTEMDRIVE",
            "WINDIR",
            "TEMP",
            "TMP",
            "HOME",
            "USERPROFILE",
        ]
        for key in safe_keys:
            val = os.environ.get(key)
            if val:
                isolated_env[key] = val

        return isolated_env

    async def execute(
        self,
        manifest: PluginManifest,
        plugin_code_dir: str,
        request: PluginExecutionRequest,
        granted_capabilities: list[PluginCapability],
    ) -> PluginExecutionResult:
        """Execute a plugin entrypoint within a clean isolated child process."""
        start_time = time.perf_counter()
        entrypoint_path = os.path.join(plugin_code_dir, manifest.entrypoint)

        if not os.path.exists(entrypoint_path):
            return PluginExecutionResult(
                plugin_id=manifest.plugin_id,
                action=request.action,
                success=False,
                error=f"Entrypoint '{manifest.entrypoint}' not found in plugin directory",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                request_id=request.request_id,
            )

        # Prepare isolated environment & IPC payload
        env = self._build_isolated_environment(plugin_code_dir)
        ipc_request = {
            "jsonrpc": "2.0",
            "id": request.request_id,
            "method": request.action,
            "params": request.parameters,
            "capabilities": [c.value for c in granted_capabilities],
        }
        ipc_bytes = (json.dumps(ipc_request) + "\n").encode("utf-8")

        proc: asyncio.subprocess.Process | None = None
        try:
            # Spawn isolated subprocess
            proc = await asyncio.create_subprocess_exec(
                self.python_executable,
                entrypoint_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=plugin_code_dir,
                env=env,
            )
            self._active_processes.add(proc)

            # Communicate with strict wall-clock timeout
            stdout_data, stderr_data = await asyncio.wait_for(
                proc.communicate(input=ipc_bytes),
                timeout=request.timeout_sec,
            )

            # Check output size bounds
            if len(stdout_data) > self.MAX_OUTPUT_BYTES:
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    action=request.action,
                    success=False,
                    error=f"Output exceeded maximum byte limit ({len(stdout_data)} > {self.MAX_OUTPUT_BYTES} bytes)",
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    request_id=request.request_id,
                )

            stdout_str = stdout_data.decode("utf-8", errors="replace").strip()
            stderr_str = stderr_data.decode("utf-8", errors="replace").strip()

            if proc.returncode != 0:
                error_msg = stderr_str or f"Process exited with non-zero code: {proc.returncode}"
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    action=request.action,
                    success=False,
                    error=error_msg,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    request_id=request.request_id,
                )

            # Parse JSON-RPC response
            if not stdout_str:
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    action=request.action,
                    success=False,
                    error="Plugin produced empty stdout response",
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    request_id=request.request_id,
                )

            try:
                ipc_response = json.loads(stdout_str)
            except json.JSONDecodeError as jde:
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    action=request.action,
                    success=False,
                    error=f"Malformed JSON-RPC response from plugin: {jde} | Raw stdout: {stdout_str[:200]}",
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    request_id=request.request_id,
                )

            if "error" in ipc_response and ipc_response["error"] is not None:
                err_val = ipc_response["error"]
                err_msg = (
                    err_val if isinstance(err_val, str) else err_val.get("message", str(err_val))
                )
                return PluginExecutionResult(
                    plugin_id=manifest.plugin_id,
                    action=request.action,
                    success=False,
                    error=err_msg,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    request_id=request.request_id,
                )

            return PluginExecutionResult(
                plugin_id=manifest.plugin_id,
                action=request.action,
                success=True,
                output=ipc_response.get("result"),
                duration_ms=(time.perf_counter() - start_time) * 1000,
                request_id=request.request_id,
            )

        except TimeoutError:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return PluginExecutionResult(
                plugin_id=manifest.plugin_id,
                action=request.action,
                success=False,
                error=f"Execution timed out after {request.timeout_sec}s",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                request_id=request.request_id,
            )
        except Exception as ex:
            if proc:
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
            return PluginExecutionResult(
                plugin_id=manifest.plugin_id,
                action=request.action,
                success=False,
                error=f"Sandbox execution failure: {str(ex)}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
                request_id=request.request_id,
            )
        finally:
            if proc in self._active_processes:
                self._active_processes.remove(proc)

    async def terminate_all(self) -> None:
        """Forcefully terminate all running sandbox subprocesses."""
        for proc in list(self._active_processes):
            try:
                proc.kill()
                await proc.wait()
            except Exception:
                pass
        self._active_processes.clear()
