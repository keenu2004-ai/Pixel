"""Serena Semantic Coding Bridge & AST Analysis Engine.

Provides symbol discovery, definition lookup, cross-file reference tracking,
unified diff generation, syntax dry-run verification, and atomic rollback tokens.
"""

import ast
import difflib
import logging
import os
from pathlib import Path
from uuid import uuid4

from packages.contracts.coding import (
    PatchResult,
    SymbolDefinition,
    SymbolKind,
    SymbolLocation,
    SymbolReference,
)

logger = logging.getLogger(__name__)


class SerenaBridge:
    """Semantic coding engine using Python AST and repository indexer."""

    def __init__(self, workspace_root: str | Path = ".") -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self._rollback_store: dict[str, tuple[Path, str]] = {}

    def _resolve_safe_path(self, relative_path: str | Path) -> Path:
        """Resolves path and enforces strict workspace sandbox boundary."""
        target = (self.workspace_root / relative_path).resolve()
        try:
            target.relative_to(self.workspace_root)
        except ValueError as err:
            raise PermissionError(
                f"Path '{relative_path}' escapes workspace sandbox '{self.workspace_root}'"
            ) from err
        return target

    # -----------------------------------------------------------------------
    # 1. Symbol Extraction & Inspection
    # -----------------------------------------------------------------------

    def extract_symbols_from_file(self, file_path: str | Path) -> list[SymbolDefinition]:
        """Parses a Python file and returns all top-level and method symbol definitions."""
        safe_path = self._resolve_safe_path(file_path)
        if not safe_path.exists() or not safe_path.is_file() or safe_path.suffix != ".py":
            return []

        try:
            content = safe_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(safe_path))
        except Exception as err:
            logger.warning("Failed to parse AST for %s: %s", safe_path, err)
            return []

        symbols: list[SymbolDefinition] = []
        rel_path = str(safe_path.relative_to(self.workspace_root))

        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                params = [arg.arg for arg in node.args.args]
                sig = f"def {node.name}({', '.join(params)})"
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind=SymbolKind.FUNCTION,
                        location=SymbolLocation(
                            file_path=rel_path,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            start_col=node.col_offset,
                        ),
                        signature=sig,
                        docstring=ast.get_docstring(node),
                        parameters=params,
                    )
                )

            elif isinstance(node, ast.ClassDef):
                cls_sig = f"class {node.name}"
                symbols.append(
                    SymbolDefinition(
                        name=node.name,
                        kind=SymbolKind.CLASS,
                        location=SymbolLocation(
                            file_path=rel_path,
                            start_line=node.lineno,
                            end_line=node.end_lineno or node.lineno,
                            start_col=node.col_offset,
                        ),
                        signature=cls_sig,
                        docstring=ast.get_docstring(node),
                    )
                )

                # Class methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                        m_params = [arg.arg for arg in item.args.args]
                        m_sig = f"def {item.name}({', '.join(m_params)})"
                        symbols.append(
                            SymbolDefinition(
                                name=f"{node.name}.{item.name}",
                                kind=SymbolKind.METHOD,
                                location=SymbolLocation(
                                    file_path=rel_path,
                                    start_line=item.lineno,
                                    end_line=item.end_lineno or item.lineno,
                                    start_col=item.col_offset,
                                ),
                                signature=m_sig,
                                docstring=ast.get_docstring(item),
                                parent_symbol=node.name,
                                parameters=m_params,
                            )
                        )

        return symbols

    def search_symbols(
        self,
        query: str,
        symbol_kind: SymbolKind | None = None,
        max_results: int = 20,
    ) -> list[SymbolDefinition]:
        """Searches symbols across all Python files in the workspace matching query."""
        results: list[SymbolDefinition] = []
        q_lower = query.lower().strip()

        for root, dirs, files in os.walk(self.workspace_root):
            # Skip hidden and cache dirs
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("__pycache__", "venv", ".venv", "node_modules")
            ]
            for f in files:
                if f.endswith(".py"):
                    full_path = Path(root) / f
                    file_symbols = self.extract_symbols_from_file(full_path)
                    for sym in file_symbols:
                        if q_lower in sym.name.lower() or (
                            sym.docstring and q_lower in sym.docstring.lower()
                        ):
                            if symbol_kind is None or sym.kind == symbol_kind:
                                results.append(sym)
                                if len(results) >= max_results:
                                    return results

        return results

    def find_references(self, symbol_name: str, max_results: int = 50) -> list[SymbolReference]:
        """Searches textual and AST references to a symbol across workspace files."""
        refs: list[SymbolReference] = []
        target_name = symbol_name.split(".")[-1]  # Support both method and function name

        for root, dirs, files in os.walk(self.workspace_root):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".")
                and d not in ("__pycache__", "venv", ".venv", "node_modules")
            ]
            for f in files:
                if f.endswith((".py", ".md", ".json", ".toml")):
                    full_path = Path(root) / f
                    try:
                        lines = full_path.read_text(encoding="utf-8").splitlines()
                    except Exception:
                        continue

                    rel_path = str(full_path.relative_to(self.workspace_root))
                    for line_idx, line in enumerate(lines, start=1):
                        if target_name in line:
                            # Context snippet (line +/- 1)
                            start_ctx = max(0, line_idx - 2)
                            end_ctx = min(len(lines), line_idx + 1)
                            snippet = "\n".join(lines[start_ctx:end_ctx])

                            refs.append(
                                SymbolReference(
                                    symbol_name=symbol_name,
                                    file_path=rel_path,
                                    line_number=line_idx,
                                    line_content=line.strip(),
                                    context_snippet=snippet,
                                )
                            )
                            if len(refs) >= max_results:
                                return refs

        return refs

    # -----------------------------------------------------------------------
    # 2. Safe Patching, Diff Generation & Rollback
    # -----------------------------------------------------------------------

    def apply_patch(
        self,
        file_path: str | Path,
        new_content: str,
        validate_syntax: bool = True,
    ) -> PatchResult:
        """Applies modifications to a file with syntax dry-run verification and rollback token."""
        try:
            safe_path = self._resolve_safe_path(file_path)
        except PermissionError as p_err:
            return PatchResult(
                file_path=str(file_path),
                success=False,
                error=str(p_err),
            )

        # 1. Read existing content for rollback
        original_content = ""
        if safe_path.exists():
            original_content = safe_path.read_text(encoding="utf-8")

        # 2. Syntax Dry-Run for Python files
        if validate_syntax and safe_path.suffix == ".py":
            try:
                ast.parse(new_content, filename=str(safe_path))
            except SyntaxError as syn_err:
                return PatchResult(
                    file_path=str(file_path),
                    success=False,
                    error=f"SyntaxError in modified code at line {syn_err.lineno}: {syn_err.msg}",
                )

        # 3. Generate Unified Diff
        orig_lines = original_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                new_lines,
                fromfile=f"a/{safe_path.name}",
                tofile=f"b/{safe_path.name}",
            )
        )
        diff_text = "".join(diff_lines)

        lines_added = sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        )
        lines_removed = sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        )

        # 4. Generate Rollback Token & Save State
        rollback_token = uuid4().hex
        self._rollback_store[rollback_token] = (safe_path, original_content)

        # 5. Write changes to file
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(new_content, encoding="utf-8")

        logger.info(
            "Applied patch to %s (+%d/-%d lines). Rollback token: %s",
            safe_path.name,
            lines_added,
            lines_removed,
            rollback_token,
        )

        return PatchResult(
            file_path=str(safe_path.relative_to(self.workspace_root)),
            success=True,
            diff=diff_text,
            lines_added=lines_added,
            lines_removed=lines_removed,
            rollback_token=rollback_token,
        )

    def rollback_patch(self, rollback_token: str) -> bool:
        """Reverts file modifications associated with a rollback token."""
        if rollback_token not in self._rollback_store:
            logger.warning("Rollback token '%s' not found or expired", rollback_token)
            return False

        safe_path, original_content = self._rollback_store.pop(rollback_token)
        try:
            safe_path.write_text(original_content, encoding="utf-8")
            logger.info(
                "Successfully rolled back %s using token %s", safe_path.name, rollback_token
            )
            return True
        except Exception as err:
            logger.error("Failed to restore %s during rollback: %s", safe_path.name, err)
            return False
