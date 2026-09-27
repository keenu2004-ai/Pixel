"""PIXEL — Safe Sandboxed Filesystem Tool.

Provides policy-governed filesystem operations:
- Strict sandbox path normalization & traversal attack prevention
- Bounded file read/write with size limits
- Deletion protection & audit logging
- L6 Policy Gate & L8 Verification integration
"""

import logging
from pathlib import Path

from packages.contracts.runtime import FilesystemOperationResult
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier

logger = logging.getLogger("pixel.os_control.filesystem")


class FilesystemSecurityException(PermissionError):
    """Raised when an operation attempts directory traversal or escapes sandbox root."""

    pass


class SafeFilesystemTool:
    """Sandboxed, secure filesystem controller with directory traversal protection."""

    def __init__(
        self,
        sandbox_root: str | Path | None = None,
        max_file_size_bytes: int = 10 * 1024 * 1024,  # 10 MB limit
        policy_gate: AgentPolicyGate | None = None,
        verifier: ActionVerifier | None = None,
    ) -> None:
        self.sandbox_root = Path(sandbox_root or Path.cwd()).resolve()
        self.max_file_size_bytes = max_file_size_bytes
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.verifier = verifier or ActionVerifier()

    def _resolve_and_validate_path(self, relative_or_absolute_path: str) -> Path:
        """Resolves path and asserts it remains strictly contained within sandbox_root."""
        raw_path = Path(relative_or_absolute_path)
        if raw_path.is_absolute():
            resolved = raw_path.resolve()
        else:
            resolved = (self.sandbox_root / raw_path).resolve()

        # Enforce sandbox containment
        try:
            resolved.relative_to(self.sandbox_root)
        except ValueError as err:
            raise FilesystemSecurityException(
                f"Path traversal detected: '{relative_or_absolute_path}' escapes sandbox root '{self.sandbox_root}'"
            ) from err

        return resolved

    def read_file(
        self,
        file_path: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> FilesystemOperationResult:
        """Reads contents of a file within sandbox bounds."""
        try:
            target = self._resolve_and_validate_path(file_path)
            if not target.exists():
                return FilesystemOperationResult(
                    operation="read",
                    target_path=str(target),
                    success=False,
                    error=f"File not found: {file_path}",
                )

            if not target.is_file():
                return FilesystemOperationResult(
                    operation="read",
                    target_path=str(target),
                    success=False,
                    error=f"Target is not a regular file: {file_path}",
                )

            size = target.stat().st_size
            if size > self.max_file_size_bytes:
                return FilesystemOperationResult(
                    operation="read",
                    target_path=str(target),
                    success=False,
                    error=f"File size {size} exceeds max limit {self.max_file_size_bytes} bytes",
                )

            content = target.read_text(encoding="utf-8", errors="replace")
            return FilesystemOperationResult(
                operation="read",
                target_path=str(target),
                success=True,
                size_bytes=size,
                content=content,
                state_verified=True,
            )
        except Exception as e:
            return FilesystemOperationResult(
                operation="read",
                target_path=file_path,
                success=False,
                error=str(e),
            )

    def write_file(
        self,
        file_path: str,
        content: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> FilesystemOperationResult:
        """Writes text content to a sandboxed file through L6 Policy evaluation."""
        try:
            target = self._resolve_and_validate_path(file_path)

            # L6 Policy Check
            spec = ToolSpec(
                name="filesystem_write",
                description="Write content to a file",
                risk_class=RiskClass.REVERSIBLE_WRITE,
                parameters_schema={},
            )
            decision, _ = self.policy_gate.evaluate(
                tool_spec=spec,
                arguments={"path": str(target), "content_length": len(content)},
                task_id=f"write_{target.name}",
                session_id=session_id,
                user_id=user_id,
            )

            if decision.verdict == PolicyVerdict.DENY:
                return FilesystemOperationResult(
                    operation="write",
                    target_path=str(target),
                    success=False,
                    error=f"L6 Policy Denied: {decision.reason}",
                )

            # Ensure parent directories exist
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

            # L8 State Verification
            verified = target.exists() and target.read_text(encoding="utf-8") == content

            return FilesystemOperationResult(
                operation="write",
                target_path=str(target),
                success=True,
                size_bytes=len(content.encode("utf-8")),
                state_verified=verified,
            )
        except Exception as e:
            return FilesystemOperationResult(
                operation="write",
                target_path=file_path,
                success=False,
                error=str(e),
            )

    def list_dir(
        self,
        dir_path: str = ".",
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> FilesystemOperationResult:
        """Lists directory entries within sandbox."""
        try:
            target = self._resolve_and_validate_path(dir_path)
            if not target.exists() or not target.is_dir():
                return FilesystemOperationResult(
                    operation="list",
                    target_path=str(target),
                    success=False,
                    error=f"Directory not found: {dir_path}",
                )

            entries = [f.name for f in target.iterdir()]
            return FilesystemOperationResult(
                operation="list",
                target_path=str(target),
                success=True,
                files=entries,
                state_verified=True,
            )
        except Exception as e:
            return FilesystemOperationResult(
                operation="list",
                target_path=dir_path,
                success=False,
                error=str(e),
            )

    def delete_file(
        self,
        file_path: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> FilesystemOperationResult:
        """Deletes a file within sandbox bounds with HIGH_IMPACT risk classification."""
        try:
            target = self._resolve_and_validate_path(file_path)
            if not target.exists():
                return FilesystemOperationResult(
                    operation="delete",
                    target_path=str(target),
                    success=False,
                    error=f"File not found: {file_path}",
                )

            # L6 Policy Gate
            spec = ToolSpec(
                name="filesystem_delete",
                description="Delete a file",
                risk_class=RiskClass.HIGH_IMPACT,
                parameters_schema={},
            )
            decision, _ = self.policy_gate.evaluate(
                tool_spec=spec,
                arguments={"path": str(target)},
                task_id=f"delete_{target.name}",
                session_id=session_id,
                user_id=user_id,
            )

            if decision.verdict == PolicyVerdict.DENY:
                return FilesystemOperationResult(
                    operation="delete",
                    target_path=str(target),
                    success=False,
                    error=f"L6 Policy Denied: {decision.reason}",
                )

            target.unlink()
            verified = not target.exists()

            return FilesystemOperationResult(
                operation="delete",
                target_path=str(target),
                success=True,
                state_verified=verified,
            )
        except Exception as e:
            return FilesystemOperationResult(
                operation="delete",
                target_path=file_path,
                success=False,
                error=str(e),
            )
