"""Unit tests for ToolRegistry and built-in capabilities."""

import tempfile
from pathlib import Path

import pytest

from packages.contracts.tools import ToolExecutionRequest
from services.agent_runtime.tools.builtin import (
    GetSystemInfoTool,
    LaunchAppTool,
    ListDirectoryTool,
    ReadFileTool,
    SetVolumeTool,
    WriteFileTool,
)
from services.agent_runtime.tools.registry import ToolRegistry
from services.os_control.mock_adapter import MockOSAdapter


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    mock_os = MockOSAdapter()
    reg.register_tool(ReadFileTool())
    reg.register_tool(WriteFileTool())
    reg.register_tool(ListDirectoryTool())
    reg.register_tool(SetVolumeTool(os_adapter=mock_os))
    reg.register_tool(LaunchAppTool(os_adapter=mock_os))
    reg.register_tool(GetSystemInfoTool(os_adapter=mock_os))
    return reg


def test_tool_registry_specs_and_validation(registry: ToolRegistry) -> None:
    specs = registry.list_specs()
    assert len(specs) == 6
    names = {s.name for s in specs}
    assert "read_file" in names
    assert "write_file" in names
    assert "set_volume" in names

    # Argument validation
    valid, err = registry.validate_arguments("write_file", {"path": "test.txt", "content": "hello"})
    assert valid is True
    assert err is None

    # Missing required argument
    valid, err = registry.validate_arguments("write_file", {"path": "test.txt"})
    assert valid is False
    assert "content" in str(err)


@pytest.mark.asyncio
async def test_filesystem_tool_execution(registry: ToolRegistry) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "demo.txt"

        # 1. Write file
        req_write = ToolExecutionRequest(
            tool_name="write_file",
            arguments={"path": str(test_file), "content": "PIXEL Agent Runtime Test Content"},
            session_id="s1",
            trace_id="t1",
        )
        res_write = await registry.execute_tool(req_write)
        assert res_write.success is True
        assert test_file.exists()

        # 2. Read file
        req_read = ToolExecutionRequest(
            tool_name="read_file",
            arguments={"path": str(test_file)},
            session_id="s1",
            trace_id="t1",
        )
        res_read = await registry.execute_tool(req_read)
        assert res_read.success is True
        assert "Test Content" in str(res_read.output)


@pytest.mark.asyncio
async def test_os_tool_execution(registry: ToolRegistry) -> None:
    req_vol = ToolExecutionRequest(
        tool_name="set_volume",
        arguments={"level": 75},
        session_id="s1",
        trace_id="t1",
    )
    res_vol = await registry.execute_tool(req_vol)
    assert res_vol.success is True
    assert "75%" in str(res_vol.output)
