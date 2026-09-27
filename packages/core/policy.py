"""L6 Policy & Security Evaluation Engine."""

import os

from packages.contracts.security import PolicyDecision, PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec


class PolicyEngine:
    """Evaluates whether an action is safe, requires approval, or must be denied."""

    FORBIDDEN_SHELL_PATTERNS = [
        "rm -rf",
        "mkfs",
        ":(){ :|:& };:",
        "dd if=",
        "format c:",
        "> /dev/sd",
    ]

    @classmethod
    def evaluate_tool_request(
        cls,
        tool_spec: ToolSpec,
        arguments: dict[str, object],
        is_user_confirmed: bool = False
    ) -> PolicyDecision:
        """Evaluates a tool invocation against risk policies."""
        # 1. Check for command injection in shell execution tools
        if tool_spec.name in ["execute_shell", "run_terminal"]:
            cmd = str(arguments.get("command", "")).lower()
            for dangerous in cls.FORBIDDEN_SHELL_PATTERNS:
                if dangerous in cmd:
                    return PolicyDecision(
                        verdict=PolicyVerdict.DENY,
                        risk_class=RiskClass.HIGH_IMPACT,
                        reason=f"Forbidden dangerous command pattern detected: {dangerous}"
                    )

        # 2. Check for path traversal in filesystem tools
        if tool_spec.name in ["read_file", "write_file", "delete_file"]:
            target_path = str(arguments.get("path", ""))
            norm_path = os.path.normpath(target_path)
            if ".." in norm_path or norm_path.startswith("/") or (len(norm_path) > 1 and norm_path[1] == ":"):
                # Absolute or parent path check for sandboxed relative paths
                if not arguments.get("allow_absolute", False):
                    return PolicyDecision(
                        verdict=PolicyVerdict.DENY,
                        risk_class=RiskClass.HIGH_IMPACT,
                        reason="Path traversal or unauthorized path outside sandbox detected"
                    )

        # 3. Handle Risk Classes
        if tool_spec.risk_class == RiskClass.READ:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                risk_class=RiskClass.READ,
                reason="Read-only operation auto-approved"
            )

        if tool_spec.risk_class == RiskClass.REVERSIBLE_WRITE:
            return PolicyDecision(
                verdict=PolicyVerdict.ALLOW,
                risk_class=RiskClass.REVERSIBLE_WRITE,
                reason="Reversible write operation auto-approved with notification"
            )

        if tool_spec.risk_class in [RiskClass.EXTERNAL_COMMUNICATION, RiskClass.HIGH_IMPACT]:
            if is_user_confirmed:
                return PolicyDecision(
                    verdict=PolicyVerdict.ALLOW,
                    risk_class=tool_spec.risk_class,
                    reason="User confirmed explicit execution"
                )
            return PolicyDecision(
                verdict=PolicyVerdict.REQUIRE_USER_CONFIRMATION,
                risk_class=tool_spec.risk_class,
                reason=f"Action classified as {tool_spec.risk_class.value}; requires user approval"
            )

        return PolicyDecision(
            verdict=PolicyVerdict.DENY,
            risk_class=RiskClass.HIGH_IMPACT,
            reason="Unknown risk class"
        )
