"""Unit tests for L8 ActionVerifier."""

import tempfile

import pytest

from packages.contracts.tools import ToolExecutionResult
from services.agent_runtime.verifier import ActionVerifier


@pytest.mark.asyncio
async def test_verify_write_file_success() -> None:
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        file_path = f.name
        f.write(b"Verified file content.")

    res = ToolExecutionResult(success=True, output="File saved")
    v = await ActionVerifier.verify(
        tool_name="write_file",
        arguments={"path": file_path, "content": "Verified file content."},
        result=res,
    )

    assert v.is_verified is True
    assert v.verification_type == "filesystem_state_check"
    assert v.evidence.get("exists") is True


@pytest.mark.asyncio
async def test_verify_write_file_failure() -> None:
    non_existent_path = "C:/invalid_non_existent_dir_999/fake_file.txt"
    res = ToolExecutionResult(success=True, output="Reported saved")
    v = await ActionVerifier.verify(
        tool_name="write_file",
        arguments={"path": non_existent_path, "content": "Fake content."},
        result=res,
    )

    assert v.is_verified is False
    assert "does not exist on disk" in v.details


@pytest.mark.asyncio
async def test_verify_failed_tool_execution() -> None:
    res = ToolExecutionResult(success=False, error="Process timed out")
    v = await ActionVerifier.verify(
        tool_name="launch_app",
        arguments={"app_name": "unknown_app"},
        result=res,
    )

    assert v.is_verified is False
    assert "Tool failed during execution" in v.details
