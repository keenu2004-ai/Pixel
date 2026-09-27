"""
Automated Security Vetting Pipeline for Community Skills and Plugins.

Performs:
1. Python AST static analysis for forbidden APIs, dynamic code execution, and shell spawns.
2. Secret and credential scanning in source files.
3. Manifest schema and capability permission sanity checking.
4. Structured report generation with deterministic pass/quarantine/reject policies.
"""

from __future__ import annotations

import ast
import re
from datetime import UTC, datetime

from packages.contracts.ecosystem import (
    CommunitySkillManifest,
    FindingSeverity,
    PluginCapability,
    SecurityFinding,
    SkillVettingReport,
    VettingState,
)


class DangerousASTVisitor(ast.NodeVisitor):
    """AST visitor detecting dangerous functions, modules, and execution patterns."""

    FORBIDDEN_CALLS: dict[str, tuple[FindingSeverity, str, str]] = {
        "eval": (
            FindingSeverity.CRITICAL,
            "DANGEROUS_EVAL",
            "Direct use of eval() allows arbitrary code execution",
        ),
        "exec": (
            FindingSeverity.CRITICAL,
            "DANGEROUS_EXEC",
            "Direct use of exec() allows arbitrary code execution",
        ),
        "compile": (
            FindingSeverity.HIGH,
            "DANGEROUS_COMPILE",
            "Use of compile() for dynamic code generation",
        ),
        "__import__": (
            FindingSeverity.HIGH,
            "DANGEROUS_IMPORT",
            "Dynamic __import__ bypasses static module checks",
        ),
    }

    FORBIDDEN_MODULES: dict[str, tuple[FindingSeverity, str, str]] = {
        "subprocess": (
            FindingSeverity.CRITICAL,
            "FORBIDDEN_SUBPROCESS",
            "Subprocess spawning is forbidden inside sandboxed plugins",
        ),
        "os.system": (
            FindingSeverity.CRITICAL,
            "FORBIDDEN_OS_SYSTEM",
            "os.system shell execution is forbidden",
        ),
        "os.popen": (
            FindingSeverity.CRITICAL,
            "FORBIDDEN_OS_POPEN",
            "os.popen shell execution is forbidden",
        ),
        "ctypes": (
            FindingSeverity.CRITICAL,
            "FORBIDDEN_CTYPES",
            "ctypes allows native memory manipulation and sandbox escapes",
        ),
        "pty": (FindingSeverity.CRITICAL, "FORBIDDEN_PTY", "pty allocation is forbidden"),
    }

    def __init__(self, filename: str):
        self.filename = filename
        self.findings: list[SecurityFinding] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct function calls (e.g. eval(...))
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
            if call_name in self.FORBIDDEN_CALLS:
                sev, code, msg = self.FORBIDDEN_CALLS[call_name]
                self.findings.append(
                    SecurityFinding(
                        code=code,
                        severity=sev,
                        message=msg,
                        file=self.filename,
                        line=node.lineno,
                        rule_id=f"RULE_{code}",
                    )
                )

        # Check attribute calls (e.g. os.system(...))
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                full_attr = f"{node.func.value.id}.{node.func.attr}"
                if full_attr in self.FORBIDDEN_MODULES:
                    sev, code, msg = self.FORBIDDEN_MODULES[full_attr]
                    self.findings.append(
                        SecurityFinding(
                            code=code,
                            severity=sev,
                            message=msg,
                            file=self.filename,
                            line=node.lineno,
                            rule_id=f"RULE_{code}",
                        )
                    )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            mod_name = alias.name.split(".")[0]
            if mod_name in self.FORBIDDEN_MODULES:
                sev, code, msg = self.FORBIDDEN_MODULES[mod_name]
                self.findings.append(
                    SecurityFinding(
                        code=code,
                        severity=sev,
                        message=f"Import of forbidden module '{alias.name}': {msg}",
                        file=self.filename,
                        line=node.lineno,
                        rule_id=f"RULE_{code}",
                    )
                )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            mod_name = node.module.split(".")[0]
            if mod_name in self.FORBIDDEN_MODULES:
                sev, code, msg = self.FORBIDDEN_MODULES[mod_name]
                self.findings.append(
                    SecurityFinding(
                        code=code,
                        severity=sev,
                        message=f"Import from forbidden module '{node.module}': {msg}",
                        file=self.filename,
                        line=node.lineno,
                        rule_id=f"RULE_{code}",
                    )
                )
        self.generic_visit(node)


class SkillVettingPipeline:
    """Automated security analysis engine evaluating community skill artifacts."""

    SECRET_PATTERNS: list[tuple[str, str, FindingSeverity]] = [
        (r"sk-[a-zA-Z0-9]{20,}", "OPENAI_SECRET_KEY", FindingSeverity.CRITICAL),
        (r"xox[baprs]-[0-9a-zA-Z]{10,}", "SLACK_API_TOKEN", FindingSeverity.CRITICAL),
        (r"ghp_[a-zA-Z0-9]{36}", "GITHUB_PAT", FindingSeverity.CRITICAL),
        (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "PRIVATE_KEY_BLOCK", FindingSeverity.CRITICAL),
        (r"(?i)password\s*=\s*['\"][^'\"]{8,}['\"]", "HARDCODED_PASSWORD", FindingSeverity.HIGH),
    ]

    def scan_source_code(
        self, source_code: str, filename: str = "main.py"
    ) -> list[SecurityFinding]:
        """Perform AST and regex scanning on Python source text."""
        findings: list[SecurityFinding] = []

        # 1. Regex Secret Scan
        lines = source_code.splitlines()
        for line_num, line in enumerate(lines, 1):
            for pattern, code, severity in self.SECRET_PATTERNS:
                if re.search(pattern, line):
                    findings.append(
                        SecurityFinding(
                            code=f"EXPOSED_SECRET_{code}",
                            severity=severity,
                            message=f"Potential hardcoded secret matching pattern '{code}'",
                            file=filename,
                            line=line_num,
                            rule_id="RULE_NO_EMBEDDED_SECRETS",
                        )
                    )

        # 2. Python AST Analysis
        try:
            tree = ast.parse(source_code, filename=filename)
            visitor = DangerousASTVisitor(filename)
            visitor.visit(tree)
            findings.extend(visitor.findings)
        except SyntaxError as se:
            findings.append(
                SecurityFinding(
                    code="SYNTAX_ERROR",
                    severity=FindingSeverity.CRITICAL,
                    message=f"Source code has invalid Python syntax: {se}",
                    file=filename,
                    line=se.lineno,
                    rule_id="RULE_VALID_SYNTAX",
                )
            )

        return findings

    def vet_skill(
        self,
        manifest: CommunitySkillManifest,
        source_code_by_file: dict[str, str],
    ) -> SkillVettingReport:
        """Run full vetting pipeline across all files and manifest specifications."""
        all_findings: list[SecurityFinding] = []

        # Scan each source file
        for filename, code in source_code_by_file.items():
            if filename.endswith(".py"):
                all_findings.extend(self.scan_source_code(code, filename))

        # Check for dangerous capability combinations
        caps = set(manifest.capabilities)
        if PluginCapability.READ_CONVERSATION in caps and PluginCapability.NETWORK_OUTBOUND in caps:
            all_findings.append(
                SecurityFinding(
                    code="HIGH_RISK_CAPABILITY_COMBINATION",
                    severity=FindingSeverity.MEDIUM,
                    message="Skill requests both READ_CONVERSATION and NETWORK_OUTBOUND (potential exfiltration risk)",
                    rule_id="RULE_CAPABILITY_AUDIT",
                )
            )

        # Determine decision state
        critical_count = sum(1 for f in all_findings if f.severity == FindingSeverity.CRITICAL)
        high_count = sum(1 for f in all_findings if f.severity == FindingSeverity.HIGH)
        medium_count = sum(1 for f in all_findings if f.severity == FindingSeverity.MEDIUM)

        if critical_count > 0:
            state = VettingState.REJECTED
            passed = False
        elif high_count > 0:
            state = VettingState.QUARANTINED
            passed = False
        elif medium_count > 0:
            state = VettingState.PASSED_WITH_WARNINGS
            passed = True
        else:
            state = VettingState.PASSED
            passed = True

        return SkillVettingReport(
            manifest_id=manifest.skill_id,
            state=state,
            findings=all_findings,
            vetted_at=datetime.now(UTC),
            scanner_version="1.0.0",
            passed=passed,
            details={
                "critical_findings": critical_count,
                "high_findings": high_count,
                "medium_findings": medium_count,
                "total_files_scanned": len(source_code_by_file),
            },
        )
