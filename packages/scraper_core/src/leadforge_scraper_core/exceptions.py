"""Custom exception hierarchy for the scraper core.

Each exception carries source and context so logs are actionable.
"""

from __future__ import annotations

from typing import Any


class ScraperError(Exception):
    """Base exception for all scraper failures.

    Subclass this for source-specific or phase-specific errors so callers
    can catch at whatever granularity they need.
    """

    source: str = "unknown"

    def __init__(
        self,
        message: str,
        *,
        source: str | None = None,
        url: str | None = None,
        **context: Any,
    ) -> None:
        self.message = message
        self.url = url
        self.context = context
        if source is not None:
            self.source = source
        super().__init__(self.message)

    def to_log_dict(self) -> dict[str, Any]:
        """Structured dict suitable for structlog.bind()."""
        d: dict[str, Any] = {"message": self.message, "source": self.source}
        if self.url:
            d["url"] = self.url
        d.update(self.context)
        return d


class RateLimitError(ScraperError):
    """Raised when a source responds with 429 or otherwise signals back-off."""

    def __init__(
        self,
        message: str = "Rate limit hit",
        *,
        source: str | None = None,
        url: str | None = None,
        retry_after: float | None = None,
        **context: Any,
    ) -> None:
        self.retry_after = retry_after  # seconds to wait
        super().__init__(message, source=source, url=url, retry_after=retry_after, **context)


class ProxyError(ScraperError):
    """Raised when a proxy is dead, timing out, or returning nonsense."""

    def __init__(
        self,
        message: str = "Proxy failed",
        *,
        proxy: str | None = None,
        source: str | None = None,
        url: str | None = None,
        **context: Any,
    ) -> None:
        self.proxy = proxy
        super().__init__(message, source=source, url=url, proxy=proxy, **context)


class ParseError(ScraperError):
    """Raised when none of the extraction strategies can parse the page."""

    def __init__(
        self,
        message: str = "Parse failed",
        *,
        source: str | None = None,
        url: str | None = None,
        selector_used: str | None = None,
        **context: Any,
    ) -> None:
        self.selector_used = selector_used
        super().__init__(message, source=source, url=url, selector_used=selector_used, **context)


class CircuitOpenError(ScraperError):
    """Raised when a source's circuit breaker is open."""

    def __init__(
        self,
        message: str = "Circuit breaker open",
        *,
        source: str | None = None,
        url: str | None = None,
        **context: Any,
    ) -> None:
        super().__init__(message, source=source, url=url, **context)


class CacheError(ScraperError):
    """Raised when the cache layer misbehaves (connection, serialization, etc.)."""

    pass
