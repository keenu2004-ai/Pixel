"""Semantic Coding Tools for PIXEL Agent Runtime.

Provides Serena AST symbol search, definition inspection, cross-file reference tracking,
safe syntax-checked patching with rollback tokens, and isolated pytest execution.
"""

import time
from typing import Any

from packages.contracts.coding import SymbolKind
from packages.contracts.tools import AuditLevel, RiskClass, ToolExecutionResult, ToolSpec
from packages.core.interfaces.tools import BaseTool
from services.coding.serena_bridge import SerenaBridge
from services.coding.test_runner import IsolatedTestRunner


class SemanticCodeSearchTool(BaseTool):
    """Tool for searching code symbols across workspace Python files."""

    def __init__(self, bridge: SerenaBridge) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="semantic_code_search",
            description="Searches code symbols (functions, classes, methods) in workspace using AST.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Symbol name or substring to search for",
                    },
                    "symbol_kind": {
                        "type": "string",
                        "enum": ["function", "method", "class", "variable", "module", "interface"],
                        "description": "Optional symbol kind filter",
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 20,
                        "description": "Max results to return",
                    },
                },
                "required": ["query"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        query = arguments.get("query", "")
        kind_str = arguments.get("symbol_kind")
        symbol_kind = SymbolKind(kind_str) if kind_str else None
        max_results = arguments.get("max_results", 20)

        results = self.bridge.search_symbols(
            query=query, symbol_kind=symbol_kind, max_results=max_results
        )
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[s.model_dump() for s in results],
            duration_ms=duration_ms,
            evidence={"count": len(results), "query": query},
        )


class InspectSymbolTool(BaseTool):
    """Tool for inspecting symbols and AST signatures within a specific file."""

    def __init__(self, bridge: SerenaBridge) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="inspect_symbol",
            description="Extracts detailed symbol definitions, signatures, docstrings, and line numbers from a file.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative workspace file path to inspect",
                    },
                },
                "required": ["file_path"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        file_path = arguments.get("file_path", "")
        try:
            symbols = self.bridge.extract_symbols_from_file(file_path)
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolExecutionResult(
                success=True,
                output=[s.model_dump() for s in symbols],
                duration_ms=duration_ms,
                evidence={"file_path": file_path, "symbol_count": len(symbols)},
            )
        except Exception as err:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolExecutionResult(
                success=False,
                error=str(err),
                duration_ms=duration_ms,
            )


class FindReferencesTool(BaseTool):
    """Tool for locating cross-file references and call-sites of a symbol."""

    def __init__(self, bridge: SerenaBridge) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="find_references",
            description="Finds references and call sites of a symbol across repository source and test files.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "Name of the symbol to locate",
                    },
                    "max_results": {
                        "type": "integer",
                        "default": 50,
                        "description": "Maximum number of references",
                    },
                },
                "required": ["symbol_name"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        symbol_name = arguments.get("symbol_name", "")
        max_results = arguments.get("max_results", 50)

        refs = self.bridge.find_references(symbol_name=symbol_name, max_results=max_results)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ToolExecutionResult(
            success=True,
            output=[r.model_dump() for r in refs],
            duration_ms=duration_ms,
            evidence={"symbol_name": symbol_name, "references_found": len(refs)},
        )


class ApplyCodePatchTool(BaseTool):
    """Tool for safely applying code modifications with syntax checks and rollback tokens."""

    def __init__(self, bridge: SerenaBridge) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="apply_code_patch",
            description="Applies modifications to a workspace file with AST syntax validation and rollback token generation.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Workspace file path to modify"},
                    "new_content": {
                        "type": "string",
                        "description": "Complete new content for the file",
                    },
                    "validate_syntax": {
                        "type": "boolean",
                        "default": True,
                        "description": "Whether to enforce ast.parse syntax checking",
                    },
                },
                "required": ["file_path", "new_content"],
            },
            timeout_ms=10000,
            requires_approval=False,
            audit_level=AuditLevel.DETAILED,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        file_path = arguments.get("file_path", "")
        new_content = arguments.get("new_content", "")
        validate_syntax = arguments.get("validate_syntax", True)

        patch_res = self.bridge.apply_patch(file_path, new_content, validate_syntax=validate_syntax)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        if not patch_res.success:
            return ToolExecutionResult(
                success=False,
                error=patch_res.error,
                duration_ms=duration_ms,
                evidence={"file_path": file_path},
            )

        return ToolExecutionResult(
            success=True,
            output=patch_res.model_dump(),
            duration_ms=duration_ms,
            evidence={
                "patch_id": patch_res.patch_id,
                "lines_added": patch_res.lines_added,
                "lines_removed": patch_res.lines_removed,
                "rollback_token": patch_res.rollback_token,
                "diff": patch_res.diff,
            },
        )


class RollbackCodePatchTool(BaseTool):
    """Tool for atomic restoration of previous file content using rollback token."""

    def __init__(self, bridge: SerenaBridge) -> None:
        self.bridge = bridge

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="rollback_code_patch",
            description="Reverts a file patch using its rollback token.",
            risk_class=RiskClass.REVERSIBLE_WRITE,
            parameters_schema={
                "type": "object",
                "properties": {
                    "rollback_token": {
                        "type": "string",
                        "description": "Rollback token returned by apply_code_patch",
                    },
                },
                "required": ["rollback_token"],
            },
            timeout_ms=5000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        token = arguments.get("rollback_token", "")
        success = self.bridge.rollback_patch(token)
        duration_ms = int((time.perf_counter() - start_time) * 1000)

        return ToolExecutionResult(
            success=success,
            output={"rolled_back": success, "rollback_token": token},
            error=None if success else f"Invalid or expired rollback token: '{token}'",
            duration_ms=duration_ms,
        )


class RunTestsTool(BaseTool):
    """Tool for running targeted or workspace pytest suites in isolation."""

    def __init__(self, runner: IsolatedTestRunner) -> None:
        self.runner = runner

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="run_isolated_tests",
            description="Executes pytest tests in a sandboxed process with failure parsing.",
            risk_class=RiskClass.READ,
            parameters_schema={
                "type": "object",
                "properties": {
                    "test_paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of test files or nodes to run",
                    },
                    "filter_expr": {
                        "type": "string",
                        "description": "Optional keyword expression filter (-k)",
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "default": 30,
                        "description": "Execution timeout",
                    },
                },
            },
            timeout_ms=45000,
            requires_approval=False,
            audit_level=AuditLevel.BASIC,
        )

    async def execute(self, arguments: dict[str, Any], session_id: str) -> ToolExecutionResult:
        start_time = time.perf_counter()
        test_paths = arguments.get("test_paths")
        filter_expr = arguments.get("filter_expr")
        timeout_seconds = arguments.get("timeout_seconds", 30)

        try:
            result = self.runner.run_tests(
                test_paths=test_paths,
                filter_expr=filter_expr,
                timeout_seconds=timeout_seconds,
            )
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            return ToolExecutionResult(
                success=result.all_passed,
                output=result.model_dump(),
                error=None
                if result.all_passed
                else f"{result.failed} tests failed, {result.errors} errors",
                duration_ms=duration_ms,
                evidence={
                    "passed": result.passed,
                    "failed": result.failed,
                    "errors": result.errors,
                    "exit_code": result.exit_code,
                },
            )
        except Exception as err:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            return ToolExecutionResult(
                success=False,
                error=str(err),
                duration_ms=duration_ms,
            )
