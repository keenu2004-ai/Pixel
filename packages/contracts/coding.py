"""Semantic Coding, AST Symbol, and Test Runner Contracts.

Defines schemas for Serena MCP semantic code operations, AST symbol inspection,
patch generation, and isolated test runner execution.
"""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


def _gen_id() -> str:
    return uuid4().hex


def _utc_now() -> datetime:
    return datetime.now(UTC)


class SymbolKind(StrEnum):
    """Categorization of code symbols."""

    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    VARIABLE = "variable"
    MODULE = "module"
    INTERFACE = "interface"


class SymbolLocation(BaseModel):
    """File and line coordinates for a code symbol."""

    file_path: str = Field(..., description="Relative or canonical file path")
    start_line: int = Field(..., ge=1, description="Start line (1-indexed)")
    end_line: int = Field(..., ge=1, description="End line (1-indexed)")
    start_col: int = Field(default=0, ge=0, description="Start column index")
    end_col: int = Field(default=0, ge=0, description="End column index")


class SymbolDefinition(BaseModel):
    """Detailed symbol definition extracted from AST."""

    name: str = Field(..., description="Symbol identifier name")
    kind: SymbolKind = Field(..., description="Symbol category")
    location: SymbolLocation = Field(..., description="File coordinates")
    signature: str = Field(default="", description="Function signature or class definition header")
    docstring: str | None = Field(default=None, description="Extracted docstring if present")
    parent_symbol: str | None = Field(default=None, description="Enclosing class or module name")
    parameters: list[str] = Field(
        default_factory=list, description="Parameter names if function/method"
    )
    return_type: str | None = Field(default=None, description="Type annotation for return value")


class SymbolReference(BaseModel):
    """Usage reference of a symbol across repository files."""

    symbol_name: str = Field(..., description="Name of referenced symbol")
    file_path: str = Field(..., description="Path to file where symbol is referenced")
    line_number: int = Field(..., ge=1, description="Line number of usage")
    line_content: str = Field(..., description="Source line content")
    context_snippet: str = Field(default="", description="Surrounding code snippet for context")


class PatchResult(BaseModel):
    """Result of applying a code modification/patch."""

    patch_id: str = Field(default_factory=_gen_id, description="Unique patch transaction ID")
    file_path: str = Field(..., description="Target file path")
    success: bool = Field(..., description="Whether patch applied cleanly without syntax errors")
    diff: str = Field(default="", description="Unified diff of applied changes")
    lines_added: int = Field(default=0, ge=0)
    lines_removed: int = Field(default=0, ge=0)
    rollback_token: str | None = Field(
        default=None, description="Token to revert patch if verification fails"
    )
    error: str | None = Field(default=None, description="Error details if patch failed")
    created_at: datetime = Field(default_factory=_utc_now)


class TestFailureDetail(BaseModel):
    """Structured breakdown of an individual test failure."""

    test_name: str = Field(
        ..., description="Full test identifier (e.g. tests/unit/test_x.py::test_y)"
    )
    error_message: str = Field(..., description="Primary error or assertion message")
    traceback: str = Field(default="", description="Captured failure traceback")


class TestExecutionResult(BaseModel):
    """Structured output from isolated test runner execution."""

    passed: int = Field(default=0, ge=0, description="Count of passing tests")
    failed: int = Field(default=0, ge=0, description="Count of failed tests")
    errors: int = Field(default=0, ge=0, description="Count of collection/import errors")
    skipped: int = Field(default=0, ge=0, description="Count of skipped tests")
    total: int = Field(default=0, ge=0, description="Total tests collected")
    duration_ms: int = Field(default=0, ge=0, description="Execution time in milliseconds")
    exit_code: int = Field(default=0, description="Process exit code")
    all_passed: bool = Field(
        default=False, description="True if passed > 0 and failed == 0 and errors == 0"
    )
    failures: list[TestFailureDetail] = Field(
        default_factory=list, description="Parsed failure details"
    )
    raw_output: str = Field(default="", description="Truncated raw stdout/stderr")
