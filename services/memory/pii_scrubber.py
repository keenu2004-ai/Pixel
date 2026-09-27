"""High-Precision PII and Secret Redaction Engine.

Scrubs API keys, passwords, authentication tokens, emails, phone numbers,
and financial information before persistence in memory or knowledge stores.
"""

import logging
import re
from typing import Any

from packages.contracts.memory import PIIScrubResult

logger = logging.getLogger(__name__)


class PIIScrubber:
    """Deterministic PII and secret redaction engine."""

    # 1. API Keys and Credentials
    SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("OPENAI_KEY", re.compile(r"\bsk-[a-zA-Z0-9_-]{20,}\b", re.IGNORECASE)),
        ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
        ("GITHUB_TOKEN", re.compile(r"\bghp_[a-zA-Z0-9]{36}\b")),
        ("BEARER_TOKEN", re.compile(r"\bBearer\s+[a-zA-Z0-9_\-\.]{20,}\b", re.IGNORECASE)),
        ("PASSWORD_ASSIGN", re.compile(r"\b(?:password|passwd|pwd|secret|api_key|token)\s*[:=]\s*['\"]?([^\s'\"]+)['\"]?", re.IGNORECASE)),
    ]

    # 2. Financial & Personal Identifiers
    PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
        ("EMAIL", re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")),
        ("PHONE_IN", re.compile(r"(?:(?<=\D)|(?<=^))(?:\+91[-\s]?)?[6-9]\d{9}\b")),
        ("PHONE_INTL", re.compile(r"(?:(?<=\D)|(?<=^))\+?[1-9]\d{0,2}[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")),
        ("CREDIT_CARD", re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")),
        ("AADHAAR", re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")),
    ]

    @classmethod
    def scrub(cls, text: str) -> PIIScrubResult:
        """Sanitizes text by replacing detected secrets and PII with safe category markers."""
        if not text:
            return PIIScrubResult(cleaned_text="", detected_entities=[], has_secrets=False, redaction_count=0)

        cleaned = text
        detected: list[dict[str, Any]] = []
        has_secrets = False
        redaction_count = 0

        # Scrub Secrets
        for label, pattern in cls.SECRET_PATTERNS:
            matches = list(pattern.finditer(cleaned))
            if matches:
                has_secrets = True
                for m in matches:
                    detected.append({"type": label, "start": m.start(), "end": m.end()})
                    redaction_count += 1
                cleaned = pattern.sub(f"[REDACTED_{label}]", cleaned)

        # Scrub PII
        for label, pattern in cls.PII_PATTERNS:
            matches = list(pattern.finditer(cleaned))
            if matches:
                for m in matches:
                    detected.append({"type": label, "start": m.start(), "end": m.end()})
                    redaction_count += 1
                cleaned = pattern.sub(f"[REDACTED_{label}]", cleaned)

        return PIIScrubResult(
            cleaned_text=cleaned,
            detected_entities=detected,
            has_secrets=has_secrets,
            redaction_count=redaction_count,
        )
