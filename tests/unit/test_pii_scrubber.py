"""Unit tests for PII and Secret Redaction Engine."""

from services.memory.pii_scrubber import PIIScrubber


def test_scrub_api_keys_and_passwords() -> None:
    text = "My OpenAI key is sk-abcdef1234567890abcdef123456 and password is password='superSecret123!'"
    res = PIIScrubber.scrub(text)

    assert res.has_secrets is True
    assert res.redaction_count >= 2
    assert "sk-abcdef" not in res.cleaned_text
    assert "superSecret123!" not in res.cleaned_text
    assert "[REDACTED_OPENAI_KEY]" in res.cleaned_text


def test_scrub_personal_identifiers() -> None:
    text = "Contact me at user.test@example.com or call +919876543210 or card 4111-2222-3333-4444."
    res = PIIScrubber.scrub(text)

    assert res.redaction_count >= 3
    assert "user.test@example.com" not in res.cleaned_text
    assert "9876543210" not in res.cleaned_text
    assert "4111-2222-3333-4444" not in res.cleaned_text
    assert "[REDACTED_EMAIL]" in res.cleaned_text
    assert "[REDACTED_PHONE_IN]" in res.cleaned_text
    assert "[REDACTED_CREDIT_CARD]" in res.cleaned_text


def test_clean_text_no_redactions() -> None:
    text = "I love programming in Python and working on PIXEL."
    res = PIIScrubber.scrub(text)

    assert res.has_secrets is False
    assert res.redaction_count == 0
    assert res.cleaned_text == text
