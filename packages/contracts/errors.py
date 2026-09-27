"""Structured Error Model Contracts for PIXEL.

Provides a unified, lightweight exception and error hierarchy across all subsystem boundaries.
"""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCategory(StrEnum):
    """Classification of errors across PIXEL boundaries."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    POLICY_DENIAL = "POLICY_DENIAL"
    TOOL_EXECUTION_ERROR = "TOOL_EXECUTION_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_ERROR = "PROVIDER_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ErrorPayload(BaseModel):
    """Serializable error representation for IPC, WebSockets, and API responses."""
    category: ErrorCategory = Field(..., description="Error category classification")
    message: str = Field(..., description="Human-readable description of error")
    code: str = Field(..., description="Stable programmatic error code")
    details: dict[str, Any] = Field(default_factory=dict, description="Structured error context")
    retryable: bool = Field(default=False, description="Whether the operation can be retried")


class PixelException(Exception):
    """Base exception for all PIXEL domain errors."""
    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL_ERROR,
        code: str = "PIXEL_INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        retryable: bool = False
    ) -> None:
        super().__init__(message)
        self.payload = ErrorPayload(
            category=category,
            message=message,
            code=code,
            details=details or {},
            retryable=retryable
        )


class PolicyDenialException(PixelException):
    """Raised when an operation is blocked by the L6 Policy Engine."""
    def __init__(self, reason: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=f"Action denied by security policy: {reason}",
            category=ErrorCategory.POLICY_DENIAL,
            code="PIXEL_POLICY_DENIAL",
            details=details,
            retryable=False
        )


class ToolExecutionException(PixelException):
    """Raised when a tool execution fails."""
    def __init__(self, tool_name: str, error: str, retryable: bool = False) -> None:
        super().__init__(
            message=f"Tool '{tool_name}' failed: {error}",
            category=ErrorCategory.TOOL_EXECUTION_ERROR,
            code="PIXEL_TOOL_FAILURE",
            details={"tool_name": tool_name, "raw_error": error},
            retryable=retryable
        )


class ProviderTimeoutException(PixelException):
    """Raised when an external speech or model provider times out."""
    def __init__(self, provider_name: str, timeout_ms: int) -> None:
        super().__init__(
            message=f"Provider '{provider_name}' timed out after {timeout_ms}ms",
            category=ErrorCategory.PROVIDER_TIMEOUT,
            code="PIXEL_PROVIDER_TIMEOUT",
            details={"provider": provider_name, "timeout_ms": timeout_ms},
            retryable=True
        )
