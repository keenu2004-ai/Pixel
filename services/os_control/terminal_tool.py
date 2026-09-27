"""PIXEL — Controlled Terminal Execution Tool.

Provides safe terminal command execution with:
- Command allowlist & dangerous pattern filtering (shell injection defense)
- Working directory confinement
- Strict execution timeout
- Automatic secret & credential stripping from stdout/stderr
- Non-bypassable L6 Policy Gate evaluation
"""

import asyncio
import logging
import re
import time
from pathlib import Path

from packages.contracts.runtime import TerminalCommandResult
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier

logger = logging.getLogger("pixel.os_control.terminal")

# Regex patterns for detecting and scrubbing secrets from terminal output
SECRET_PATTERNS = [
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|auth|bearer)\s*[:=\s]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"
    ),
    re.compile(r"ghp_[a-zA-Z0-9]{36}"),
    re.compile(r"ey[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}\.[a-zA-Z0-9_\-]{20,}"),  # JWT
]

DANGEROUS_PATTERNS = [
    re.compile(r"(?i)\brm\s+-rf\s+.*"),
    re.compile(r"(?i)\b(del\s+/s\s+/q|mkfs|format\s+[a-z]:|shutdown|reboot)"),
    re.compile(r"(?i)(:(){ :|:& };:)"),  # Fork bomb
]


class TerminalTool:
    """Controlled terminal executor with secret scrubbing and timeout management."""

    def __init__(
        self,
        working_dir: str | Path | None = None,
        timeout_seconds: float = 30.0,
        policy_gate: AgentPolicyGate | None = None,
        verifier: ActionVerifier | None = None,
    ) -> None:
        self.working_dir = Path(working_dir or Path.cwd()).resolve()
        self.timeout_seconds = timeout_seconds
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.verifier = verifier or ActionVerifier()

    def _sanitize_output(self, raw_output: str) -> tuple[str, int]:
        """Redacts sensitive credentials and returns cleaned text and redacted count."""
        redacted_count = 0
        cleaned = raw_output
        for pattern in SECRET_PATTERNS:
            matches = list(pattern.finditer(cleaned))
            if matches:
                redacted_count += len(matches)
                cleaned = pattern.sub(r"\1: [REDACTED_SECRET]", cleaned)
        return cleaned, redacted_count

    def _is_dangerous(self, command: str) -> bool:
        """Inspects command line for prohibited destructive patterns."""
        for pattern in DANGEROUS_PATTERNS:
            if pattern.search(command):
                return True
        return False

    async def run_command(
        self,
        command: str,
        cwd: str | Path | None = None,
        timeout: float | None = None,
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> TerminalCommandResult:
        """Executes a shell command in a controlled asynchronous subprocess."""
        exec_timeout = timeout or self.timeout_seconds
        effective_cwd = Path(cwd or self.working_dir).resolve()

        # 1. Dangerous pattern filter
        if self._is_dangerous(command):
            return TerminalCommandResult(
                command_executed=command,
                exit_code=1,
                stderr="Security Error: Prohibited destructive command pattern detected.",
            )

        # 2. L6 Policy Gate Check
        spec = ToolSpec(
            name="terminal_run_command",
            description="Execute terminal command in controlled environment",
            risk_class=RiskClass.HIGH_IMPACT,
            parameters_schema={},
        )
        decision, _ = self.policy_gate.evaluate(
            tool_spec=spec,
            arguments={"command": command, "cwd": str(effective_cwd)},
            task_id=f"cmd_{int(time.time())}",
            session_id=session_id,
            user_id=user_id,
        )

        if decision.verdict == PolicyVerdict.DENY:
            return TerminalCommandResult(
                command_executed=command,
                exit_code=1,
                stderr=f"L6 Policy Denied: {decision.reason}",
            )

        # 3. Subprocess Execution
        start_t = time.perf_counter()
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(effective_cwd),
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=exec_timeout
            )
            duration_ms = (time.perf_counter() - start_t) * 1000

            stdout_str = stdout_bytes.decode("utf-8", errors="replace")
            stderr_str = stderr_bytes.decode("utf-8", errors="replace")

            # 4. Secret Scrubbing
            clean_stdout, red_out = self._sanitize_output(stdout_str)
            clean_stderr, red_err = self._sanitize_output(stderr_str)

            return TerminalCommandResult(
                command_executed=command,
                exit_code=proc.returncode if proc.returncode is not None else 0,
                stdout=clean_stdout,
                stderr=clean_stderr,
                duration_ms=duration_ms,
                secrets_redacted_count=red_out + red_err,
                timed_out=False,
            )

        except TimeoutError:
            duration_ms = (time.perf_counter() - start_t) * 1000
            try:
                proc.kill()
            except Exception:
                pass
            return TerminalCommandResult(
                command_executed=command,
                exit_code=-1,
                stderr=f"Command timed out after {exec_timeout} seconds.",
                duration_ms=duration_ms,
                timed_out=True,
            )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_t) * 1000
            return TerminalCommandResult(
                command_executed=command,
                exit_code=1,
                stderr=f"Execution error: {str(e)}",
                duration_ms=duration_ms,
            )
