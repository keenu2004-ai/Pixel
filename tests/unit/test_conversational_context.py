"""Unit tests for ConversationalContextManager."""

import pytest

from packages.contracts.mobile import AndroidContact
from services.intent_engine.conversational_context import (
    AmbiguityException,
    ConversationalContextManager,
)


def test_contact_ambiguity_detection() -> None:
    manager = ConversationalContextManager()

    contacts = [
        AndroidContact(display_name="Rahul Sharma", phone_number="+919876543210"),
        AndroidContact(display_name="Rahul Verma", phone_number="+919123456789"),
    ]

    # Ambiguous match must raise AmbiguityException rather than guessing
    with pytest.raises(AmbiguityException) as exc_info:
        manager.resolve_contact_ambiguity("Rahul", contacts)

    assert "Multiple contacts found" in str(exc_info.value)
    assert "Rahul Sharma" in str(exc_info.value)
    assert "Rahul Verma" in str(exc_info.value)


def test_single_contact_resolution() -> None:
    manager = ConversationalContextManager()
    contacts = [
        AndroidContact(display_name="Mom", phone_number="+919999999999"),
    ]
    resolved = manager.resolve_contact_ambiguity("Mom", contacts)
    assert resolved.display_name == "Mom"
    assert resolved.phone_number == "+919999999999"


def test_conversational_commands() -> None:
    manager = ConversationalContextManager()

    # Cancel command
    cancel_res = manager.handle_conversational_commands("cancel that")
    assert cancel_res is not None
    assert cancel_res["command"] == "CANCEL"

    # Repeat without previous action
    repeat_empty = manager.handle_conversational_commands("do that again")
    assert repeat_empty is not None
    assert repeat_empty["command"] == "REPEAT_UNAVAILABLE"

    # Record action then repeat
    manager.record_action("SET_ALARM", {"time": "07:00"})
    repeat_valid = manager.handle_conversational_commands("do that again")
    assert repeat_valid is not None
    assert repeat_valid["command"] == "REPEAT"
    assert repeat_valid["action"] == "SET_ALARM"

    # Forget recent turn
    manager.record_turn("What is my schedule?", "You have 2 meetings.")
    assert len(manager._recent_turns) == 1
    forget_res = manager.handle_conversational_commands("forget what i just said")
    assert forget_res is not None
    assert forget_res["command"] == "FORGET_RECENT"
    assert len(manager._recent_turns) == 0
