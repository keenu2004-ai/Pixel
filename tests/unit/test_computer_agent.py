"""Unit tests for ComputerAgent desktop workflow execution."""

import pytest

from packages.contracts.agent import AgentExecutionStatus
from services.computer_control.computer_agent import ComputerAgent
from services.computer_control.desktop_adapter import DesktopAdapter


@pytest.mark.asyncio
async def test_computer_agent_focus_workflow() -> None:
    adapter = DesktopAdapter(mock_mode=True)
    agent = ComputerAgent(adapter=adapter)

    state = await agent.execute_task(
        user_query="Switch to Chrome browser",
        target_app="chrome",
        action="focus",
    )

    assert state.status == AgentExecutionStatus.SUCCESS
    assert state.plan is not None
    assert state.plan.is_complete is True
    assert state.last_verification is not None
    assert state.last_verification.is_verified is True


@pytest.mark.asyncio
async def test_computer_agent_clipboard_write_workflow() -> None:
    adapter = DesktopAdapter(mock_mode=True)
    agent = ComputerAgent(adapter=adapter)

    state = await agent.execute_task(
        user_query="Copy generated token to clipboard",
        target_app=None,
        action="clipboard_write",
        clipboard_text="SECURE_TOKEN_XYZ_123",
    )

    assert state.status == AgentExecutionStatus.SUCCESS
    assert adapter.read_clipboard().text == "SECURE_TOKEN_XYZ_123"


@pytest.mark.asyncio
async def test_computer_agent_missing_app_fails() -> None:
    adapter = DesktopAdapter(mock_mode=True)
    agent = ComputerAgent(adapter=adapter)

    state = await agent.execute_task(
        user_query="Switch to nonexistent app",
        target_app="NonExistentSuperApp",
        action="focus",
    )

    assert state.status == AgentExecutionStatus.FAILED
    assert "Failed to find or focus" in (state.error or "")
