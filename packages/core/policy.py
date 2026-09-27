"""L6 Policy & Security Evaluation Engine."""

import hashlib
import json
import os
from typing import Any

from packages.contracts.security import AuditRecord, PolicyDecision, PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec


class PolicyEngine:
    """Evaluates whether a tool execution is permitted, denied, or requires explicit confirmation."""

    FORBIDDEN_SHELL_PATTERNS = [
        "rm -rf",
        "mkfs",
        ":(){ :|:& };:",
        "dd if=",
        "format c:",
        "> /dev/sd",
        "shutdown",
        "reboot",
    ]

    @classmethod
    def evaluate_tool_request(
        cls, tool_spec: ToolSpec, arguments: dict[str, Any], is_user_confirmed: bool = False
    ) -> PolicyDecision:
        """Evaluates a tool invocation against risk policies."""
        # 1. Shell command security check
        if tool_spec.name in ["execute_shell", "run_terminal", "run_command"]:
            cmd = str(arguments.get("command", "")).lower()
            for dangerous in cls.FORBIDDEN_SHELL_PATTERNS:
                if dangerous in cmd:
                    return PolicyDecision(
                        verdict=PolicyVerdict.DENY,
                        risk_class=RiskClass.HIGH_IMPACT,
                        reason=f"Forbidden dangerous command pattern detected: {dangerous}",
                    )

        # 2. Filesystem sandbox & path traversal check
        if tool_spec.name in [
            "read_file",
            "write_file",
            "delete_file",
            "edit_code",
            "apply_code_patch",
            "inspect_symbol",
        ]:
            target_path = str(arguments.get("path") or arguments.get("file_path") or "").lower()
            norm_path = os.path.normpath(target_path)
            forbidden_system_dirs = [
                "/etc",
                "/sys",
                "/proc",
                "/root",
                "/boot",
                "/dev",
                "c:\\windows",
                "c:\\boot",
                "c:\\recovery",
                ".git",
                ".env",
            ]
            if ".." in norm_path or any(
                norm_path.startswith(d) or f"/{d}" in norm_path or f"\\{d}" in norm_path
                for d in forbidden_system_dirs
            ):
                if not arguments.get("allow_absolute", False):
                    return PolicyDecision(
                        verdict=PolicyVerdict.DENY,
                        risk_class=RiskClass.HIGH_IMPACT,
                        reason="Path traversal or unauthorized path outside sandbox detected",
                    )

            # High-impact diff threshold check for code patching (> 50 lines modified)
            if tool_spec.name == "apply_code_patch":
                new_content = str(arguments.get("new_content", ""))
                line_count = len(new_content.splitlines())
                if line_count > 50 and not is_user_confirmed:
                    return PolicyDecision(
                        verdict=PolicyVerdict.REQUIRE_USER_CONFIRMATION,
                        risk_class=RiskClass.HIGH_IMPACT,
                        reason=f"Code modification exceeds 50 lines threshold ({line_count} lines); requires explicit confirmation",
                    )

        # 3. Handle explicit tool requirement for approval
        if tool_spec.requires_approval and not is_user_confirmed:
            return PolicyDecision(
                verdict=PolicyVerdict.REQUIRE_USER_CONFIRMATION,
                risk_class=tool_spec.risk_class,
                reason=f"Tool '{tool_spec.name}' explicitly requires user confirmation",
            )

        # 4. Handle Risk Classes
        if tool_spec.risk_class == RiskClass.READ:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                risk_class=RiskClass.READ,
                reason="Read-only operation auto-approved",
            )

        if tool_spec.risk_class == RiskClass.REVERSIBLE_WRITE:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                risk_class=RiskClass.REVERSIBLE_WRITE,
                reason="Reversible write operation auto-approved with notification",
            )

        if tool_spec.risk_class in [RiskClass.EXTERNAL_COMMUNICATION, RiskClass.HIGH_IMPACT]:
            if is_user_confirmed:
                return PolicyDecision(
                    verdict=PolicyVerdict.ALLOW,
                    risk_class=tool_spec.risk_class,
                    reason="User confirmed explicit execution",
                )
            return PolicyDecision(
                verdict=PolicyVerdict.REQUIRE_USER_CONFIRMATION,
                risk_class=tool_spec.risk_class,
                reason=f"Action classified as {tool_spec.risk_class.value}; requires user approval",
            )

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            risk_class=RiskClass.HIGH_IMPACT,
            reason="Unknown risk class",
        )

    @classmethod
    def create_audit_record(
        cls,
        actor_id: str,
        tool_spec: ToolSpec,
        arguments: dict[str, Any],
        decision: PolicyDecision,
        trace_id: str,
        execution_success: bool | None = None,
    ) -> AuditRecord:
        """Generates an immutable audit trail record."""
        # Hash arguments for privacy preservation while ensuring auditability
        try:
            serialized_args = json.dumps(arguments, sort_keys=True, default=str)
        except Exception:
            serialized_args = str(arguments)

        args_hash = hashlib.sha256(serialized_args.encode("utf-8")).hexdigest()

        return AuditRecord(
            actor_id=actor_id,
            tool_name=tool_spec.name,
            arguments_hash=args_hash,
            risk_class=decision.risk_class,
            verdict=decision.verdict,
            audit_level=tool_spec.audit_level,
            execution_success=execution_success,
            trace_id=trace_id,
        )
