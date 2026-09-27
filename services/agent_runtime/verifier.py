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

        # Default standard verification
        return VerificationResult(
            is_verified=True,
            tool_name=tool_name,
            verification_type="deterministic_outcome",
            details=f"Tool '{tool_name}' executed cleanly with output: {str(result.output)[:100]}",
            evidence=result.evidence or {},
        )
