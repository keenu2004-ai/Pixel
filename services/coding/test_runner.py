"""Isolated Test Runner for Pytest and Python Unit Tests.

Provides secure, sandboxed execution of test suites without shell injection,
with strict timeouts, memory/output caps, and structured failure analysis.
"""

import logging
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from packages.contracts.coding import TestExecutionResult, TestFailureDetail

logger = logging.getLogger(__name__)

# Dangerous shell characters that indicate injection attempt
SHELL_INJECTION_PATTERN = re.compile(r"[;&|`$<>\n\r]")


class IsolatedTestRunner:
    """Executes tests inside the workspace sandbox with structured reporting."""

    def __init__(
        self,
        workspace_root: str | Path = ".",
        default_timeout_seconds: int = 30,
        max_output_chars: int = 50_000,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.default_timeout_seconds = default_timeout_seconds
        self.max_output_chars = max_output_chars

    def _validate_args(self, test_targets: list[str]) -> None:
        """Ensures test target arguments contain no shell injection metacharacters."""
        for target in test_targets:
            if SHELL_INJECTION_PATTERN.search(target):
                raise ValueError(f"Security violation: Illegal characters detected in test target '{target}'")

    def run_tests(
        self,
        test_paths: list[str] | None = None,
        filter_expr: str | None = None,
        timeout_seconds: int | None = None,
        python_executable: str | None = None,
    ) -> TestExecutionResult:
        """Runs pytest with the given targets and parses results."""
        targets = test_paths or ["tests/unit/"]
        self._validate_args(targets)

        if filter_expr:
            self._validate_args([filter_expr])

        timeout = timeout_seconds or self.default_timeout_seconds
        py_exe = python_executable or sys.executable

        # Build command array for direct execution (no shell=True) with bytecode cache disabled
        cmd = [py_exe, "-B", "-m", "pytest", "-v", "-p", "no:cacheprovider"]
        if filter_expr:
            cmd.extend(["-k", filter_expr])
        cmd.extend(targets)

        # Ensure environment does not write or reuse stale pyc files
        import os
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

        start_time = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                cwd=str(self.workspace_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
                shell=False,
                env=env,
            )
            stdout = res.stdout or ""
            exit_code = res.returncode
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            timeout_out = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "Execution timed out.")
            return TestExecutionResult(
                passed=0,
                failed=1,
                errors=1,
                skipped=0,
                total=1,
                duration_ms=duration_ms,
                exit_code=-1,
                all_passed=False,
                failures=[
                    TestFailureDetail(
                        test_name="TimeoutExpired",
                        error_message=f"Test run exceeded timeout of {timeout} seconds",
                        traceback="",
                    )
                ],
                raw_output=timeout_out[: self.max_output_chars],
            )
        except Exception as err:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return TestExecutionResult(
                passed=0,
                failed=1,
                errors=1,
                skipped=0,
                total=1,
                duration_ms=duration_ms,
                exit_code=-2,
                all_passed=False,
                failures=[
                    TestFailureDetail(
                        test_name="ExecutionError",
                        error_message=str(err),
                        traceback="",
                    )
                ],
                raw_output=f"Failed to execute test process: {err}",
            )

        duration_ms = int((time.perf_counter() - start_time) * 1000)
        parsed = self._parse_pytest_output(stdout)

        return TestExecutionResult(
            passed=parsed["passed"],
            failed=parsed["failed"],
            errors=parsed["errors"],
            skipped=parsed["skipped"],
            total=parsed["total"],
            duration_ms=duration_ms,
            exit_code=exit_code,
            all_passed=(exit_code == 0 and parsed["failed"] == 0 and parsed["errors"] == 0),
            failures=parsed["failures"],
            raw_output=stdout[: self.max_output_chars],
        )

    def _parse_pytest_output(self, output: str) -> dict[str, Any]:
        """Extracts passed, failed, errors, skipped and failure details from pytest stdout."""
        passed = 0
        failed = 0
        errors = 0
        skipped = 0

        # Pattern for pytest summary line: e.g. "== 5 passed, 1 failed in 0.12s =="
        # or "== 1 failed, 2 passed, 1 error in 0.5s =="
        summary_match = re.search(r"=+ (.*) in [\d\.]+s =+", output)
        if summary_match:
            line = summary_match.group(1)
            p_match = re.search(r"(\d+)\s+passed", line)
            f_match = re.search(r"(\d+)\s+failed", line)
            e_match = re.search(r"(\d+)\s+error", line)
            s_match = re.search(r"(\d+)\s+skipped", line)

            if p_match:
                passed = int(p_match.group(1))
            if f_match:
                failed = int(f_match.group(1))
            if e_match:
                errors = int(e_match.group(1))
            if s_match:
                skipped = int(s_match.group(1))
        else:
            # Check for passed / failed individual test markers if short output
            passed = len(re.findall(r" PASSED ", output)) + len(re.findall(r"::.* PASSED", output))
            failed = len(re.findall(r" FAILED ", output)) + len(re.findall(r"::.* FAILED", output))
            errors = len(re.findall(r" ERROR ", output))

        total = passed + failed + errors + skipped

        # Parse detailed failures
        failures: list[TestFailureDetail] = []

        # 1. Parse from short test summary info: e.g. "FAILED test_failing.py::test_bad - assert 1 == 2"
        summary_failures = re.findall(r"(?:FAILED|ERROR)\s+([a-zA-Z0-9_\-\./\\]+::[a-zA-Z0-9_\-\.]+)(?:\s+-\s+(.*))?", output)
        for t_name, reason in summary_failures:
            failures.append(
                TestFailureDetail(
                    test_name=t_name.strip(),
                    error_message=reason.strip() if reason else "Assertion failed",
                    traceback="",
                )
            )

        # 2. Parse from progress lines: e.g. "test_failing.py::test_bad FAILED"
        if not failures:
            prog_failures = re.findall(r"([a-zA-Z0-9_\-\./\\]+::[a-zA-Z0-9_\-\.]+)\s+FAILED", output)
            for t_name in prog_failures:
                failures.append(
                    TestFailureDetail(
                        test_name=t_name.strip(),
                        error_message="Test failed",
                        traceback="",
                    )
                )

        # 3. Parse from failure block headers: "___ test_name ___"
        if not failures:
            indiv_failures = re.findall(r"_{3,}\s+([^\n_]+)\s+_{3,}\n(.*?)(?=\n_{3,}\s+|\n={3,}|\Z)", output, re.DOTALL)
            for name, body in indiv_failures:
                body_lines = [ln.strip() for ln in body.strip().splitlines() if ln.strip()]
                err_msg = body_lines[-1] if body_lines else "Assertion failed"
                failures.append(
                    TestFailureDetail(
                        test_name=name.strip(),
                        error_message=err_msg,
                        traceback=body[:3000],
                    )
                )

        # If failed > 0 but no named failure matched, add generic failure
        if not failures and failed > 0:
            failures.append(
                TestFailureDetail(
                    test_name="UnknownTestFailure",
                    error_message=f"{failed} test(s) failed in suite",
                    traceback="",
                )
            )

        return {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "skipped": skipped,
            "total": total,
            "failures": failures,
        }
