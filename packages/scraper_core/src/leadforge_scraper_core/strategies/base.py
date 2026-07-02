"""ExtractionStrategy protocol (abstract base class).

Each concrete strategy implements:
  - name: human-readable label for logging
  - priority: lower = runs first (0 = highest)
  - can_handle(html): fast check if strategy is applicable
  - extract(html, url): returns StrategyResult or None
  - is_fallback: True for the last-resort strategy (AI)

The pipeline composes strategies and short-circuits on first non-None result.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StrategyResult:
    """Result returned by a successful extraction.

    Fields are optional — strategies only populate what they can extract.
    Consumers merge results from multiple strategies.
    """

    name: str | None = None
    category: str | None = None
    address: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    phone: str | None = None
    website: str | None = None
    rating: float | None = None
    review_count: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    email: str | None = None
    social_handles: dict[str, str] = field(default_factory=dict)
    # Raw confidence score 0–100 for this result
    confidence: int = 50
    # Which strategy produced this result
    strategy_name: str = ""
    # Additional key-value metadata from the page
    extras: dict[str, Any] = field(default_factory=dict)

    def merge_with(self, other: StrategyResult) -> StrategyResult:
        """Merge two results, preferring non-None values from self."""
        if not other:
            return self
        self_fields = [
            "name",
            "category",
            "address",
            "city",
            "state",
            "country",
            "postal_code",
            "phone",
            "website",
            "rating",
            "review_count",
            "latitude",
            "longitude",
            "email",
        ]
        for f in self_fields:
            if getattr(self, f) is None:
                setattr(self, f, getattr(other, f))
        if not self.social_handles and other.social_handles:
            self.social_handles = other.social_handles
        self.confidence = max(self.confidence, other.confidence)
        self.extras.update(other.extras)
        return self


class ExtractionStrategy(ABC):
    """Abstract base class for HTML extraction strategies."""

    # Human-readable name for logging
    name: str = "base"
    # Lower = higher priority (runs first)
    priority: int = 99
    # If True, this is the last-resort strategy (e.g. AI fallback)
    is_fallback: bool = False

    @abstractmethod
    def can_handle(self, html: str) -> bool:
        """Return True if this strategy can likely extract data from the page.

        Used for fast early-exit in the pipeline.  Default implementation
        returns True so strategies that always apply can skip override.
        """

    @abstractmethod
    async def extract(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
    ) -> StrategyResult | None:
        """Extract structured data from *html*.

        Args:
            html: Raw HTML of the page.
            url: URL the HTML was fetched from (for context/absolute resolution).
            logger: Optional structlog logger for detailed diagnostics.

        Returns:
            StrategyResult if extraction succeeded, None otherwise.
        """

    async def run(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
    ) -> StrategyResult | None:
        """Wrapper that calls extract() and logs success/failure.

        Subclasses can override for pre/post processing.
        """
        try:
            result = await self.extract(html, url, logger=logger)
            if logger and result:
                logger.debug(
                    "extraction.success",
                    strategy=self.name,
                    url=url,
                    confidence=result.confidence,
                )
            return result
        except Exception as exc:
            if logger:
                logger.warning(
                    "extraction.failed",
                    strategy=self.name,
                    url=url,
                    error=str(exc),
                )
            return None


def create_pipeline(strategies: list[ExtractionStrategy]) -> list[ExtractionStrategy]:
    """Return strategies sorted by priority."""
    return sorted(strategies, key=lambda s: s.priority)
