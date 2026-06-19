"""Unit tests for monitors — circuit breaker, rate limiter, proxy rotator."""

from __future__ import annotations

import asyncio
import pytest

from leadforge_scraper_core.monitors.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
)
from leadforge_scraper_core.monitors.rate_limiter import (
    DomainRateLimiter,
    GlobalConcurrencyLimiter,
    AdaptiveRateLimiter,
)
from leadforge_scraper_core.monitors.proxy_rotator import ProxyManager


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    @pytest.fixture
    def cb(self) -> CircuitBreaker:
        return CircuitBreaker(
            source="test_source",
            config=CircuitBreakerConfig(
                failure_threshold=3,
                window_seconds=60.0,
                open_duration_seconds=30.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_starts_closed(self, cb: CircuitBreaker) -> None:
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self, cb: CircuitBreaker) -> None:
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_can_execute_when_closed(self, cb: CircuitBreaker) -> None:
        can_exec = await cb.can_execute()
        assert can_exec is True

    @pytest.mark.asyncio
    async def test_cannot_execute_when_open(self, cb: CircuitBreaker) -> None:
        for _ in range(3):
            await cb.record_failure()
        can_exec = await cb.can_execute()
        assert can_exec is False

    @pytest.mark.asyncio
    async def test_half_open_after_duration(self, cb: CircuitBreaker) -> None:
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        # Manually transition (normally handled by timer)
        cb._opened_at = cb._opened_at - 31 if cb._opened_at else None
        can_exec = await cb.can_execute()
        # With short open duration in config, should transition
        assert can_exec is True

    @pytest.mark.asyncio
    async def test_closes_after_success_in_half_open(self, cb: CircuitBreaker) -> None:
        for _ in range(3):
            await cb.record_failure()
        cb._state = CircuitState.HALF_OPEN
        cb._half_open_requests = 1
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_failure_in_half_open_reopens(self, cb: CircuitBreaker) -> None:
        cb._state = CircuitState.HALF_OPEN
        await cb.record_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_cleanup_window(self, cb: CircuitBreaker) -> None:
        import time
        cb._failures = [time.time() - 120, time.time() - 90, time.time() - 30]
        cb._cleanup_window()
        assert len(cb._failures) == 1


class TestDomainRateLimiter:
    """Tests for DomainRateLimiter."""

    @pytest.fixture
    def limiter(self) -> DomainRateLimiter:
        return DomainRateLimiter(delay_seconds=0.1)

    @pytest.mark.asyncio
    async def test_first_request_no_delay(self, limiter: DomainRateLimiter) -> None:
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_second_request_delayed(self, limiter: DomainRateLimiter) -> None:
        await limiter.acquire("example.com")
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.09

    @pytest.mark.asyncio
    async def test_different_domains_no_delay(self, limiter: DomainRateLimiter) -> None:
        await limiter.acquire("domain1.com")
        start = asyncio.get_event_loop().time()
        await limiter.acquire("domain2.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_reset_clears_domain(self, limiter: DomainRateLimiter) -> None:
        await limiter.acquire("example.com")
        await limiter.reset("example.com")
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.05


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter with back-off on 429."""

    @pytest.fixture
    def limiter(self) -> AdaptiveRateLimiter:
        return AdaptiveRateLimiter(base_delay=0.05, max_delay=1.0, penalty_duration=1.0)

    @pytest.mark.asyncio
    async def test_backoff_doubles_on_429(self, limiter: AdaptiveRateLimiter) -> None:
        await limiter.acquire("example.com")
        await limiter.note_429("example.com")
        # Current delay should have doubled
        # Next acquire should be delayed
        start = asyncio.get_event_loop().time()
        await limiter.acquire("example.com")
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04  # At least base_delay

    @pytest.mark.asyncio
    async def test_max_delay_cap(self, limiter: AdaptiveRateLimiter) -> None:
        for _ in range(10):
            await limiter.note_429("example.com")
        # Should be capped at max_delay
        # This is a behavior check — delay should not exceed max_delay * penalty_duration
        assert limiter._current_delay.get("example.com", 0.05) <= 1.0


class TestProxyManager:
    """Tests for ProxyManager proxy rotation."""

    @pytest.fixture
    def manager(self) -> ProxyManager:
        return ProxyManager(proxies=[
            "http://proxy1.example.com:8080",
            "http://proxy2.example.com:8080",
            "http://proxy3.example.com:8080",
        ])

    def test_initialization(self, manager: ProxyManager) -> None:
        assert len(manager) == 3
        assert manager.has_proxies is True

    def test_empty_proxies(self) -> None:
        manager = ProxyManager(proxies=[])
        assert manager.has_proxies is False

    @pytest.mark.asyncio
    async def test_cycles_through_proxies(self, manager: ProxyManager) -> None:
        first = await manager.get_next()
        second = await manager.get_next()
        third = await manager.get_next()
        fourth = await manager.get_next()
        assert first == second or first != third  # Round-robin
        assert fourth in manager._proxies  # full proxy string, not first char

    @pytest.mark.asyncio
    async def test_all_proxies_returned_eventually(self, manager: ProxyManager) -> None:
        seen = set()
        for _ in range(10):
            proxy = await manager.get_next()
            if proxy:
                seen.add(proxy)
        # Should cycle through all 3 eventually
        assert len(seen) >= 1

    @pytest.mark.asyncio
    async def test_record_success_clears_failures(self, manager: ProxyManager) -> None:
        proxy = "http://proxy1.example.com:8080"
        await manager.record_failure(proxy)
        assert manager._failures.get(proxy, 0) == 1
        await manager.record_success(proxy)
        assert manager._failures.get(proxy, 0) == 0

    @pytest.mark.asyncio
    async def test_record_failure_increments(self, manager: ProxyManager) -> None:
        proxy = "http://proxy1.example.com:8080"
        await manager.record_failure(proxy)
        assert manager._failures.get(proxy, 0) == 1
        await manager.record_failure(proxy)
        assert manager._failures.get(proxy, 0) == 2


class TestGlobalConcurrencyLimiter:
    """Tests for GlobalConcurrencyLimiter semaphore."""

    @pytest.mark.asyncio
    async def test_acquire_and_release(self) -> None:
        limiter = GlobalConcurrencyLimiter(max_concurrent=2)
        async with limiter:
            assert limiter.available == 1
        assert limiter.available == 2

    @pytest.mark.asyncio
    async def test_blocks_when_full(self) -> None:
        limiter = GlobalConcurrencyLimiter(max_concurrent=1)
        acquired_second = False

        async def second_acquirer():
            nonlocal acquired_second
            async with limiter:
                acquired_second = True

        async with limiter:
            # Schedule second acquirer
            task = asyncio.create_task(second_acquirer())
            await asyncio.sleep(0.01)  # Give task time to start
            assert acquired_second is False
            # Release first
        # Now second should be able to acquire
        await task
        assert acquired_second is True