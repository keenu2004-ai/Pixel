"""Unit tests for DesktopAdapter and Desktop Tools."""

import pytest

from services.computer_control.desktop_adapter import DesktopAdapter
from services.computer_control.tools import (
    ListWindowsTool,
    ReadClipboardTool,
    WriteClipboardTool,
)


@pytest.mark.asyncio
async def test_desktop_adapter_mock_workflow() -> None:
    adapter = DesktopAdapter(mock_mode=True)

    # 1. List windows
    windows = adapter.list_windows()
    assert len(windows) >= 3
    assert any(w.app_name == "Code" for w in windows)

    # 2. Get active window
    active_win = adapter.get_active_window()
    assert active_win is not None
    assert active_win.app_name == "Code"

    # 3. Focus another window
    focused = adapter.focus_window("chrome")
    assert focused is True
    new_active = adapter.get_active_window()
    assert new_active is not None
    assert new_active.app_name == "chrome"

    # 4. Clipboard read/write
    assert adapter.write_clipboard("Pixel Voice AI") is True
    cb = adapter.read_clipboard()
    assert cb.text == "Pixel Voice AI"
    assert cb.length == 14

    # 5. Capture window
    shot = adapter.capture_window(query="chrome", redact=True)
    assert shot.app_name == "chrome"
    assert shot.is_redacted is True
    assert len(shot.data_base64) > 0


@pytest.mark.asyncio
async def test_desktop_tools_execution() -> None:
    adapter = DesktopAdapter(mock_mode=True)

    list_tool = ListWindowsTool(adapter=adapter)
    res_list = await list_tool.execute({}, session_id="test_s")
    assert res_list.success is True
    assert res_list.evidence is not None
    assert res_list.evidence["window_count"] >= 3

    write_cb_tool = WriteClipboardTool(adapter=adapter)
    res_wcb = await write_cb_tool.execute({"text": "Hello Desktop"}, session_id="test_s")
    assert res_wcb.success is True

    read_cb_tool = ReadClipboardTool(adapter=adapter)
    res_rcb = await read_cb_tool.execute({}, session_id="test_s")
    assert res_rcb.success is True
    assert isinstance(res_rcb.output, dict)
    assert res_rcb.output["text"] == "Hello Desktop"
