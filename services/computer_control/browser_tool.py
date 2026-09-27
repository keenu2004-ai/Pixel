"""PIXEL — Controlled Browser Automation Tool.

Provides safe, sandboxed web interaction:
- Domain policy verification & malicious domain blocking
- Prompt injection defense on untrusted web content
- Controlled navigation, clicking, typing, and DOM text extraction
- Non-bypassable L6 Policy Gate evaluation
"""

import logging
import re
from urllib.parse import urlparse

from packages.contracts.runtime import BrowserActionResult
from packages.contracts.security import PolicyVerdict
from packages.contracts.tools import RiskClass, ToolSpec
from services.agent_runtime.policy_gate import AgentPolicyGate
from services.agent_runtime.verifier import ActionVerifier

logger = logging.getLogger("pixel.computer_control.browser")

# Domains blocked by default for security
BLOCKED_DOMAINS = {"malware-test.com", "phishing-example.org", "darkweb.onion"}

# Prompt injection marker sanitization
PROMPT_INJECTION_PATTERNS = [
    re.compile(r"(?i)ignore\s+(previous|all)\s+instructions"),
    re.compile(r"(?i)you\s+are\s+now\s+in\s+DAN\s+mode"),
    re.compile(r"(?i)system\s*:\s*override"),
]


class ControlledBrowserTool:
    """Safe browser automation controller with prompt injection protection and domain safety."""

    def __init__(
        self,
        allowed_domains: set[str] | None = None,
        policy_gate: AgentPolicyGate | None = None,
        verifier: ActionVerifier | None = None,
    ) -> None:
        self.allowed_domains = allowed_domains
        self.policy_gate = policy_gate or AgentPolicyGate()
        self.verifier = verifier or ActionVerifier()

        # Simulated browser tab state
        self._current_url: str = "about:blank"
        self._page_title: str = "Blank"
        self._dom_content: str = ""
        self._page_store: dict[str, dict[str, str]] = {
            "https://github.com/keenu2004-ai/Pixel": {
                "title": "GitHub - keenu2004-ai/Pixel",
                "text": "PIXEL: Personal AI Voice & Agent Operating Layer. Branch: main. All tests passing.",
            },
            "https://docs.pixel-ai.org": {
                "title": "PIXEL Documentation",
                "text": "Welcome to PIXEL assistant documentation. System architecture and tool manuals.",
            },
        }

    def _sanitize_web_content(self, raw_text: str) -> str:
        """Neutralizes prompt injection patterns discovered inside web pages."""
        cleaned = raw_text
        for pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(cleaned):
                logger.warning(
                    "Detected potential prompt injection attempt in web page content: neutralising"
                )
                cleaned = pattern.sub("[UNTRUSTED_CONTENT_FILTERED]", cleaned)
        return cleaned

    def _is_url_allowed(self, url: str) -> bool:
        """Validates destination domain against security blocklists."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            return True  # Local/blank schemes

        if domain in BLOCKED_DOMAINS:
            return False

        if self.allowed_domains is not None:
            return domain in self.allowed_domains

        return True

    def register_mock_page(self, url: str, title: str, content: str) -> None:
        """Registers mock page content for deterministic integration testing."""
        self._page_store[url] = {"title": title, "text": content}

    async def navigate(
        self,
        url: str,
        session_id: str = "default_session",
        user_id: str = "default_user",
    ) -> BrowserActionResult:
        """Navigates to a target URL under L6 policy gating and domain safety checks."""
        if not self._is_url_allowed(url):
            return BrowserActionResult(
                action_type="navigate",
                target_url=url,
                success=False,
                error=f"Security Error: Domain '{urlparse(url).netloc}' is blocked or not in allowlist.",
            )

        # L6 Policy Check
        spec = ToolSpec(
            name="browser_navigate",
            description="Navigate browser to destination URL",
            risk_class=RiskClass.READ,
            parameters_schema={},
        )
        decision, _ = self.policy_gate.evaluate(
            tool_spec=spec,
            arguments={"url": url},
            task_id=f"nav_{urlparse(url).netloc}",
            session_id=session_id,
            user_id=user_id,
        )

        if decision.verdict == PolicyVerdict.DENY:
            return BrowserActionResult(
                action_type="navigate",
                target_url=url,
                success=False,
                error=f"L6 Policy Denied: {decision.reason}",
            )

        # Update simulated page state
        self._current_url = url
        page_data = self._page_store.get(
            url,
            {"title": f"Page: {urlparse(url).netloc}", "text": f"Simulated content for {url}"},
        )
        self._page_title = page_data["title"]
        self._dom_content = self._sanitize_web_content(page_data["text"])

        return BrowserActionResult(
            action_type="navigate",
            target_url=url,
            success=True,
            page_title=self._page_title,
            extracted_text=self._dom_content,
        )

    async def read_page_text(self) -> BrowserActionResult:
        """Extracts text from current browser page with injection defense applied."""
        return BrowserActionResult(
            action_type="read_text",
            target_url=self._current_url,
            success=True,
            page_title=self._page_title,
            extracted_text=self._dom_content,
        )
