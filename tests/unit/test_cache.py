"""Unit tests for RedisHTMLCache and basic scraper errors."""

from __future__ import annotations

import pytest

from leadforge_scraper_core.exceptions import (
    ScraperError,
    RateLimitError,
    ProxyError,
    ParseError,
    CircuitOpenError,
)
from leadforge_scraper_core.strategies.base import StrategyResult


class TestScraperExceptions:
    """Tests for custom exception hierarchy."""

    def test_scraper_error_context(self) -> None:
        exc = ScraperError("Something went wrong", source="yelp", url="https://yelp.com")
        assert exc.message == "Something went wrong"
        assert exc.source == "yelp"
        assert exc.url == "https://yelp.com"
        assert exc.to_log_dict()["source"] == "yelp"

    def test_rate_limit_error(self) -> None:
        exc = RateLimitError(
            "429 received",
            source="yelp",
            retry_after=30.0,
        )
        assert exc.retry_after == 30.0
        d = exc.to_log_dict()
        assert d["retry_after"] == 30.0

    def test_proxy_error(self) -> None:
        exc = ProxyError(
            "Proxy timeout",
            proxy="http://proxy:8080",
            source="playwright",
        )
        assert exc.proxy == "http://proxy:8080"

    def test_parse_error(self) -> None:
        exc = ParseError(
            "Selector failed",
            source="yelp",
            selector_used="a[href*='/biz/']",
        )
        assert exc.selector_used == "a[href*='/biz/']"

    def test_circuit_open_error(self) -> None:
        exc = CircuitOpenError(source="yelp")
        assert exc.source == "yelp"


class TestStrategyResult:
    """Tests for StrategyResult dataclass."""

    def test_default_confidence(self) -> None:
        result = StrategyResult(strategy_name="test")
        assert result.confidence == 50

    def test_merge_with(self) -> None:
        r1 = StrategyResult(name="Business A", phone=None, strategy_name="s1")
        r2 = StrategyResult(name=None, phone="+1-555-1234", strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.name == "Business A"
        assert merged.phone == "+1-555-1234"

    def test_merge_social_handles(self) -> None:
        r1 = StrategyResult(social_handles={"facebook": "biz1"}, strategy_name="s1")
        r2 = StrategyResult(social_handles={"instagram": "biz2"}, strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.social_handles == {"facebook": "biz1"}

    def test_merge_extras(self) -> None:
        r1 = StrategyResult(extras={"key1": "val1"}, strategy_name="s1")
        r2 = StrategyResult(extras={"key2": "val2"}, strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.extras["key1"] == "val1"
        assert merged.extras["key2"] == "val2"

    def test_merge_confidence_takes_higher(self) -> None:
        r1 = StrategyResult(confidence=30, strategy_name="s1")
        r2 = StrategyResult(confidence=80, strategy_name="s2")
        merged = r1.merge_with(r2)
        assert merged.confidence == 80


class TestCacheIntegration:
    """Tests for cache layer (using fakeredis for async Redis)."""

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self) -> None:
        pytest.importorskip("fakeredis")
        import fakeredis.aioredis

        from leadforge_scraper_core.cache import RedisHTMLCache

        client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        cache = RedisHTMLCache(redis_client=client, ttl_seconds=3600)

        await cache.set("https://example.com", "TestAgent/1.0", "<html>Test</html>")
        result = await cache.get("https://example.com", "TestAgent/1.0")
        assert result is not None
        assert result.decode() == "<html>Test</html>"

        await client.aclose()

    @pytest.mark.asyncio
    async def test_different_ua_different_key(self) -> None:
        pytest.importorskip("fakeredis")
        import fakeredis.aioredis

        from leadforge_scraper_core.cache import RedisHTMLCache

        client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        cache = RedisHTMLCache(redis_client=client)

        await cache.set("https://example.com", "UA1", "<html>Test</html>")
        result = await cache.get("https://example.com", "UA2")
        assert result is None  # Different UA = different key

        await client.aclose()

    @pytest.mark.asyncio
    async def test_invalidate(self) -> None:
        pytest.importorskip("fakeredis")
        import fakeredis.aioredis

        from leadforge_scraper_core.cache import RedisHTMLCache

        client = fakeredis.aioredis.FakeRedis(decode_responses=False)
        cache = RedisHTMLCache(redis_client=client)

        await cache.set("https://example.com", "UA1", "<html>Test</html>")
        await cache.invalidate("https://example.com", "UA1")
        result = await cache.get("https://example.com", "UA1")
        assert result is None

        await client.aclose()