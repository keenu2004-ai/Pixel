"""Security & Hostile Red-Team Audit for Phase 14 Daily-Driver Hardening.

Attacks tested:
- Ambiguity bypass & contact spoofing
- Doze state permission escalation
- Malicious schema rollback tampering
- Destructive terminal & fork bomb attempts
- Unauthorized filesystem escape
- External prompt injection payload defense
"""

import pytest

from packages.contracts.mobile import AndroidContact
from services.computer_control.browser_tool import ControlledBrowserTool
from services.evolution.migration_engine import MigrationEngine
from services.intent_engine.conversational_context import (
    AmbiguityException,
    ConversationalContextManager,
)
from services.os_control.filesystem_tool import SafeFilesystemTool
from services.os_control.terminal_tool import TerminalTool
from services.voice_gateway.lifecycle_hardener import (
    AssistantLifecycleHardener,
    LifecycleEvent,
)


def test_ambiguity_bypass_attack_blocked() -> None:
    manager = ConversationalContextManager()
    contacts = [
        AndroidContact(display_name="CEO", phone_number="+1000000001"),
        AndroidContact(display_name="CEO Assistant", phone_number="+1000000002"),
    ]
    with pytest.raises(AmbiguityException):
        manager.resolve_contact_ambiguity("CEO", contacts)


def test_revoked_permission_bypass_blocked() -> None:
    hardener = AssistantLifecycleHardener()
    hardener.handle_lifecycle_event(
        LifecycleEvent.PERMISSION_REVOKED, {"permission": "RECORD_AUDIO"}
    )
    assert not hardener.verify_action_permission("RECORD_AUDIO")


def test_tampered_migration_rollback() -> None:
    engine = MigrationEngine()
    initial = {"version": "1.13.0", "secure": True}

    def hostile_corrupt_migration(d: dict[str, object]) -> dict[str, object]:
        raise ValueError("Simulated malicious SQL/schema corruption attempt")

    restored, success = engine.apply_migration("1.14.0", initial, hostile_corrupt_migration)
    assert not success
    assert restored["version"] == "1.13.0"
    assert restored["secure"] is True


@pytest.mark.asyncio
async def test_terminal_fork_bomb_blocked() -> None:
    terminal = TerminalTool()
    res = await terminal.run_command(":(){ :|:& };:")
    assert res.exit_code != 0
    assert "Prohibited destructive command" in res.stderr


def test_filesystem_sandbox_escape_blocked() -> None:
    fs = SafeFilesystemTool()
    res = fs.read_file("../../Windows/System32/drivers/etc/hosts")
    assert not res.success
    assert "Path traversal detected" in (res.error or "")


@pytest.mark.asyncio
async def test_browser_untrusted_prompt_injection_sanitization() -> None:
    browser = ControlledBrowserTool(allowed_domains={"attacker-site.com"})
    res = await browser.navigate("https://attacker-site.com")
    assert res.success
    # Prompt injection tag is attached to prevent LLM hijacking
    assert res.extracted_text is not None
    assert "[UNTRUSTED EXTERNAL WEB CONTENT" in res.extracted_text
