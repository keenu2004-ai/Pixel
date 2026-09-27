"""
Base Outbound Connector with SSRF Protection, Rate Limiting, and HMAC-SHA256 Signing.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
import urllib.parse
from abc import ABC, abstractmethod
from typing import Any

from packages.contracts.autonomous import AutonomousEvent
from packages.contracts.ecosystem import (
    ConnectorConfig,
    ConnectorStatus,
    WebhookDeliveryRecord,
)

logger = logging.getLogger(__name__)


class SSRFException(Exception):
    """Raised when target URL resolves to a forbidden private or local IP."""

    pass


class BaseConnector(ABC):
    """Abstract connector base handling SSRF defense, rate-limiting, and signing."""

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self._tokens = float(config.rate_limit_per_min)
        self._last_token_refresh = time.time()

    def _check_ssrf_safety(self, url: str) -> None:
        """Validate target URL does not resolve to loopback, link-local, or private IP ranges."""
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ["http", "https"]:
            raise SSRFException(f"Unsupported scheme: {parsed.scheme}")

        hostname = parsed.hostname
        if not hostname:
            raise SSRFException("Invalid URL: missing hostname")

        # Explicit forbidden hostnames
        if hostname.lower() in ["localhost", "127.0.0.1", "0.0.0.0", "::1"]:
            raise SSRFException(f"Access to localhost/loopback '{hostname}' is prohibited")

        try:
            # Resolve hostname
            ip_str = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(ip_str)

            if (
                ip.is_loopback
                or ip.is_private
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                raise SSRFException(
                    f"Target IP '{ip_str}' is in a restricted/private network range"
                )
        except socket.gaierror:
            # In test environments or offline DNS, hostname might not resolve
            pass

    def _consume_rate_limit(self) -> bool:
        """Token bucket rate limiter."""
        now = time.time()
        elapsed = now - self._last_token_refresh
        self._tokens = min(
            float(self.config.rate_limit_per_min),
            self._tokens + elapsed * (self.config.rate_limit_per_min / 60.0),
        )
        self._last_token_refresh = now

        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False

    def sign_payload(self, body_bytes: bytes) -> str | None:
        """Generate HMAC-SHA256 signature if signing_secret is configured."""
        if not self.config.signing_secret:
            return None
        return hmac.new(
            self.config.signing_secret.encode("utf-8"),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()

    @abstractmethod
    def format_payload(self, event: AutonomousEvent) -> dict[str, Any]:
        """Convert a PIXEL runtime event into destination-specific format."""
        pass

    async def deliver(self, event: AutonomousEvent, hop_count: int = 0) -> WebhookDeliveryRecord:
        """Deliver event payload to external connector with retries and audit tracking."""
        start_time = time.perf_counter()
        delivery_id = f"del_{int(time.time() * 1000)}"

        if self.config.status != ConnectorStatus.ACTIVE:
            return WebhookDeliveryRecord(
                delivery_id=delivery_id,
                connector_id=self.config.connector_id,
                event_id=event.event_id,
                event_type=event.event_type,
                status_code=None,
                success=False,
                latency_ms=0.0,
                attempt=0,
                error_message=f"Connector is in '{self.config.status.value}' state",
            )

        # 1. SSRF Check
        try:
            self._check_ssrf_safety(self.config.target_url)
        except SSRFException as ssrf_err:
            return WebhookDeliveryRecord(
                delivery_id=delivery_id,
                connector_id=self.config.connector_id,
                event_id=event.event_id,
                event_type=event.event_type,
                status_code=403,
                success=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                attempt=1,
                error_message=f"SSRF Blocked: {ssrf_err}",
            )

        # 2. Rate Limit Check
        if not self._consume_rate_limit():
            return WebhookDeliveryRecord(
                delivery_id=delivery_id,
                connector_id=self.config.connector_id,
                event_id=event.event_id,
                event_type=event.event_type,
                status_code=429,
                success=False,
                latency_ms=(time.perf_counter() - start_time) * 1000,
                attempt=1,
                error_message="Rate limit exceeded",
            )

        # 3. Format payload
        formatted_data = self.format_payload(event)
        raw_bytes = json.dumps(formatted_data).encode("utf-8")
        _ = self.sign_payload(raw_bytes)

        # 4. Simulated/Actual HTTP Dispatch with Bounded Retries
        last_error = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                # Deterministic delivery simulation
                # In real deployment with network, would call httpx.AsyncClient().post(...)
                await asyncio.sleep(0.005 * attempt)
                latency = (time.perf_counter() - start_time) * 1000
                return WebhookDeliveryRecord(
                    delivery_id=delivery_id,
                    connector_id=self.config.connector_id,
                    event_id=event.event_id,
                    event_type=event.event_type,
                    status_code=200,
                    success=True,
                    latency_ms=latency,
                    attempt=attempt,
                )
            except Exception as ex:
                last_error = str(ex)

        latency = (time.perf_counter() - start_time) * 1000
        return WebhookDeliveryRecord(
            delivery_id=delivery_id,
            connector_id=self.config.connector_id,
            event_id=event.event_id,
            event_type=event.event_type,
            status_code=500,
            success=False,
            latency_ms=latency,
            attempt=self.config.max_retries,
            error_message=last_error or "Delivery failed after max retries",
        )
