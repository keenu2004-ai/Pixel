"""Unit tests for SerenaBridge AST inspection, search, patching, and rollback."""

from pathlib import Path

from packages.contracts.coding import SymbolKind
from services.coding.serena_bridge import SerenaBridge


def test_serena_bridge_extract_symbols(tmp_path: Path) -> None:
    test_code = """
def sample_function(x, y):
    '''A sample function docstring.'''
    return x + y

class SampleClass:
    '''Class docstring.'''
    def sample_method(self, z):
        return z * 2
"""
    file_path = tmp_path / "sample.py"
    file_path.write_text(test_code, encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)
    symbols = bridge.extract_symbols_from_file("sample.py")

    assert len(symbols) == 3
    fn_sym = next(s for s in symbols if s.name == "sample_function")
    assert fn_sym.kind == SymbolKind.FUNCTION
    assert fn_sym.parameters == ["x", "y"]
    assert fn_sym.docstring == "A sample function docstring."

    cls_sym = next(s for s in symbols if s.name == "SampleClass")
    assert cls_sym.kind == SymbolKind.CLASS

    method_sym = next(s for s in symbols if s.name == "SampleClass.sample_method")
    assert method_sym.kind == SymbolKind.METHOD
    assert method_sym.parent_symbol == "SampleClass"


def test_serena_bridge_search_and_references(tmp_path: Path) -> None:
    code_a = """
def calculate_total(price, tax):
    return price + tax
"""
    code_b = """
from a import calculate_total

def process_order():
    return calculate_total(100, 5)
"""
    (tmp_path / "a.py").write_text(code_a, encoding="utf-8")
    (tmp_path / "b.py").write_text(code_b, encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)

    # Search
    search_results = bridge.search_symbols("calculate_total")
    assert len(search_results) >= 1
    assert search_results[0].name == "calculate_total"

    # Find references
    refs = bridge.find_references("calculate_total")
    assert len(refs) >= 2  # Definition in a.py, import/call in b.py


def test_serena_bridge_patch_and_rollback(tmp_path: Path) -> None:
    target_file = tmp_path / "module.py"
    original_code = "def old_func():\n    return 1\n"
    target_file.write_text(original_code, encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)

    # 1. Apply Valid Patch
    new_code = "def old_func():\n    return 2\n"
    res = bridge.apply_patch("module.py", new_code)
    assert res.success is True
    assert res.rollback_token is not None
    assert target_file.read_text(encoding="utf-8") == new_code

    # 2. Rollback
    rb_success = bridge.rollback_patch(res.rollback_token)
    assert rb_success is True
    assert target_file.read_text(encoding="utf-8") == original_code


def test_serena_bridge_syntax_error_rejection(tmp_path: Path) -> None:
    target_file = tmp_path / "broken.py"
    target_file.write_text("def valid(): pass\n", encoding="utf-8")

    bridge = SerenaBridge(workspace_root=tmp_path)
    broken_code = "def broken(:\n    pass\n"

    res = bridge.apply_patch("broken.py", broken_code, validate_syntax=True)
    assert res.success is False
    assert "SyntaxError" in (res.error or "")
    # Ensure original file content was NOT corrupted
    assert target_file.read_text(encoding="utf-8") == "def valid(): pass\n"
