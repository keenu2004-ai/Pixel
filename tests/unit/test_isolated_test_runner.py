"""Unit tests for IsolatedTestRunner execution, parsing, and security."""

from pathlib import Path

import pytest

from services.coding.test_runner import IsolatedTestRunner


def test_isolated_test_runner_pass(tmp_path: Path) -> None:
    test_file = tmp_path / "test_simple.py"
    test_file.write_text("def test_ok(): assert 1 == 1\n", encoding="utf-8")

    runner = IsolatedTestRunner(workspace_root=tmp_path)
    res = runner.run_tests(test_paths=["test_simple.py"])

    assert res.all_passed is True
    assert res.passed == 1
    assert res.failed == 0
    assert res.exit_code == 0


def test_isolated_test_runner_fail(tmp_path: Path) -> None:
    test_file = tmp_path / "test_failing.py"
    test_file.write_text("def test_bad(): assert 1 == 2\n", encoding="utf-8")

    runner = IsolatedTestRunner(workspace_root=tmp_path)
    res = runner.run_tests(test_paths=["test_failing.py"])

    assert res.all_passed is False
    assert res.failed >= 1
    assert len(res.failures) >= 1
    assert "test_bad" in res.failures[0].test_name


def test_isolated_test_runner_shell_injection_defense(tmp_path: Path) -> None:
    runner = IsolatedTestRunner(workspace_root=tmp_path)

    with pytest.raises(ValueError, match="Security violation"):
        runner.run_tests(test_paths=["test_foo.py; rm -rf /"])

    with pytest.raises(ValueError, match="Security violation"):
        runner.run_tests(test_paths=["test_foo.py && cat /etc/passwd"])

    with pytest.raises(ValueError, match="Security violation"):
        runner.run_tests(test_paths=["test_foo.py | echo hacked"])
