"""NaxosData SDK Exception Hierarchy."""

from __future__ import annotations
from typing import Optional, Dict, Any


class NaxosAPIError(Exception):
    """Base exception for all NaxosData API errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body or {}
        self.headers = headers or {}

    def __str__(self) -> str:
        if self.status_code:
            return f"[{self.status_code}] {self.message}"
        return self.message


class AuthenticationError(NaxosAPIError):
    """Raised when an API key is missing, invalid, or expired (HTTP 401 / 403)."""
    pass


class RateLimitError(NaxosAPIError):
    """Raised when request rate ceiling for the active tier is exceeded (HTTP 429)."""

    def __init__(
        self,
        message: str,
        status_code: int = 429,
        retry_after_sec: Optional[int] = None,
        response_body: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ):
        super().__init__(message, status_code, response_body, headers)
        self.retry_after_sec = retry_after_sec


class QuotaExceededError(NaxosAPIError):
    """Raised when monthly export row quota has been exhausted (HTTP 429 / 402)."""
    pass


class NotFoundError(NaxosAPIError):
    """Raised when the requested market, pair, or order book partition does not exist (HTTP 404)."""
    pass


class ServerError(NaxosAPIError):
    """Raised when the NaxosData API encounters an unhandled internal server error (HTTP 500+)."""
    pass
