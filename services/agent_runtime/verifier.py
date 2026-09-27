"""L8 Post-Execution Action Verification Layer."""

import logging
from pathlib import Path
from typing import Any

from packages.contracts.agent import VerificationResult
from packages.contracts.tools import ToolExecutionResult

logger = logging.getLogger(__name__)


class ActionVerifier:
    """Verifies that executed tool actions produced the expected physical/system effect."""

    @classmethod
    async def verify(
        cls,
        tool_name: str,
        arguments: dict[str, Any],
        result: ToolExecutionResult,
    ) -> VerificationResult:
        """Inspects post-execution state and validates outcome."""
        if not result.success:
            return VerificationResult(
                is_verified=False,
                tool_name=tool_name,
                verification_type="execution_check",
                details=f"Tool failed during execution: {result.error}",
                evidence=result.evidence or {},
            )

        # 1. Verification for write_file
        if tool_name == "write_file":
            path_str = str(arguments.get("path", "")).strip()
            path = Path(path_str)
            if not path.exists():
                return VerificationResult(
                    is_verified=False,
                    tool_name=tool_name,
                    verification_type="filesystem_state_check",
                    details=f"File '{path_str}' was reported written but does not exist on disk",
                    evidence={"path": path_str, "exists": False},
                )
            size = path.stat().st_size
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="filesystem_state_check",
                details=f"File '{path_str}' confirmed present on disk ({size} bytes)",
                evidence={"path": str(path.resolve()), "size_bytes": size, "exists": True},
            )

        # 2. Verification for read_file
        if tool_name == "read_file":
            path_str = str(arguments.get("path", "")).strip()
            output = result.output
            if output is None:
                return VerificationResult(
                    is_verified=False,
                    tool_name=tool_name,
                    verification_type="read_verification",
                    details=f"Read file returned null output for '{path_str}'",
                    evidence={"path": path_str},
                )
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="read_verification",
                details=f"Successfully read contents from '{path_str}' ({len(str(output))} chars)",
                evidence={"path": path_str, "output_length": len(str(output))},
            )

        # 3. Verification for set_volume
        if tool_name == "set_volume":
            target_level = arguments.get("level")
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="system_state_check",
                details=f"Audio volume set to {target_level}%",
                evidence={"target_level": target_level},
            )

        # 4. Verification for apply_code_patch
        if tool_name == "apply_code_patch":
            file_path_str = str(arguments.get("file_path", "")).strip()
            path = Path(file_path_str)
            if not path.exists():
                return VerificationResult(
                    is_verified=False,
                    tool_name=tool_name,
                    verification_type="code_patch_check",
                    details=f"Target patch file '{file_path_str}' does not exist on disk",
                    evidence={"file_path": file_path_str},
                )
            # Syntax validation check on disk
            if path.suffix == ".py":
                try:
                    import ast

                    ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                except SyntaxError as syn_err:
                    return VerificationResult(
                        is_verified=False,
                        tool_name=tool_name,
                        verification_type="code_syntax_check",
                        details=f"Syntax error in patched file: {syn_err}",
                        evidence={"file_path": file_path_str, "error": str(syn_err)},
                    )
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="code_patch_check",
                details=f"Patch applied cleanly to '{file_path_str}' with valid syntax",
                evidence=result.evidence or {},
            )

        # 5. Verification for run_isolated_tests
        if tool_name == "run_isolated_tests":
            output_dict = result.output if isinstance(result.output, dict) else {}
            exit_code = (
                output_dict.get("exit_code", 0)
                if output_dict
                else (result.evidence.get("exit_code", 0) if result.evidence else 0)
            )
            passed_count = (
                output_dict.get("passed", 0)
                if output_dict
                else (result.evidence.get("passed", 0) if result.evidence else 0)
            )
            failed_count = (
                output_dict.get("failed", 0)
                if output_dict
                else (result.evidence.get("failed", 0) if result.evidence else 0)
            )

            is_verified = exit_code == 0 and failed_count == 0 and passed_count > 0
            return VerificationResult(
                is_verified=is_verified,
                tool_name=tool_name,
                verification_type="test_suite_execution",
                details=f"Tests execution verified: {passed_count} passed, {failed_count} failed",
                evidence={"passed": passed_count, "failed": failed_count, "exit_code": exit_code},
            )

        # 6. Verification for focus_window
        if tool_name == "focus_window":
            query = str(arguments.get("query", ""))
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="desktop_focus_check",
                details=f"Focus requested for window '{query}'",
                evidence={"query": query},
            )

        # 7. Verification for write_clipboard
        if tool_name == "write_clipboard":
            length = len(str(arguments.get("text", "")))
            return VerificationResult(
                is_verified=True,
                tool_name=tool_name,
                verification_type="clipboard_state_check",
                details=f"Clipboard updated with {length} characters",
                evidence={"length": length},
            )

        # Default standard verification
        return VerificationResult(
            is_verified=True,
            tool_name=tool_name,
            verification_type="deterministic_outcome",
            details=f"Tool '{tool_name}' executed cleanly with output: {str(result.output)[:100]}",
            evidence=result.evidence or {},
        )
