"""CircuitBreaker — prevents cascading failures when a source goes down.

State machine:
  CLOSED (normal) → OPEN (source failing) → HALF_OPEN (probe) → CLOSED or OPEN

Opened when: 50 failures in a 10-minute rolling window.
Stays open for: 30 minutes, then transitions to HALF_OPEN for a probe request.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import redis.asyncio as redis
from leadforge_config import get_redis_client

from leadforge_scraper_core.exceptions import CircuitOpenError


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 50
    window_seconds: float = 600.0
    open_duration_seconds: float = 1800.0
    half_open_max_requests: int = 3


@dataclass
class CircuitBreaker:
    """Per-source circuit breaker with Redis-backed state sharing across workers."""

    source: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # In-memory sliding window (also mirrored in Redis for cross-worker awareness)
    _failures: list[float] = field(default_factory=list)
    _state: CircuitState = field(default=CircuitState.CLOSED)
    _opened_at: float | None = field(default=None)
    _half_open_requests: int = 0

    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # Redis key prefix
    _PREFIX = "scraper:circuit"

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def failure_rate(self) -> float:
        """Recent failure rate per minute."""
        now = time.time()
        cutoff = now - self.config.window_seconds
        recent = [t for t in self._failures if t > cutoff]
        return len(recent) / (self.config.window_seconds / 60.0)

    async def _redis_key(self) -> tuple[str, str, str, redis.Redis]:
        client = get_redis_client(decode_responses=True)
        state_key = f"{self._PREFIX}:state:{self.source}"
        failures_key = f"{self._PREFIX}:failures:{self.source}"
        opened_key = f"{self._PREFIX}:opened_at:{self.source}"
        return state_key, failures_key, opened_key, client

    async def _load_state(self) -> None:
        """Load circuit state from Redis on startup."""
        try:
            state_key, failures_key, opened_key, client = await self._redis_key()
            state_val = await client.get(state_key)
            if state_val:
                self._state = CircuitState(state_val)
            opened_val = await client.get(opened_key)
            if opened_val:
                self._opened_at = float(opened_val)
            # Load failures
            raw = await client.lrange(failures_key, 0, -1)  # type: ignore[misc]
            self._failures = [float(t) for t in raw]
            await client.aclose()
        except Exception:
            pass

    async def record_success(self) -> None:
        """Record a successful request, potentially closing the circuit."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_requests -= 1
                if self._half_open_requests <= 0:
                    await self._close_circuit()
            elif self._state == CircuitState.CLOSED:
                # Trim old failures from the window
                self._cleanup_window()

    async def record_failure(self, exc: Exception | None = None) -> None:
        """Record a failed request, potentially opening the circuit."""
        async with self._lock:
            now = time.time()
            self._failures.append(now)

            self._cleanup_window()

            if self._state == CircuitState.HALF_OPEN:
                await self._open_circuit()
            elif self._state == CircuitState.CLOSED:
                if len(self._failures) >= self.config.failure_threshold:
                    await self._open_circuit()

            # Persist to Redis
            await self._persist_state()

    async def can_execute(self) -> bool:
        """Return True if a request is allowed through the circuit."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            if self._state == CircuitState.OPEN:
                # Check if open duration has elapsed
                if (
                    self._opened_at
                    and (time.time() - self._opened_at) >= self.config.open_duration_seconds
                ):
                    await self._half_open_circuit()
                    return True
                return False
            if self._state == CircuitState.HALF_OPEN:
                return self._half_open_requests < self.config.half_open_max_requests
            return False

    async def execute(self, coro: Any) -> Any:
        """Wrap a coroutine with circuit breaker protection.

        Raises CircuitOpenError if the circuit is open.
        """
        if not await self.can_execute():
            raise CircuitOpenError(
                f"Circuit breaker open for {self.source}",
                source=self.source,
            )
        try:
            result = await coro
            await self.record_success()
            return result
        except Exception as exc:
            await self.record_failure(exc)
            raise

    async def _open_circuit(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = time.time()
        import structlog

        log = structlog.get_logger("scraper.circuit_breaker")
        log.warning(
            "circuit.open",
            source=self.source,
            failure_count=len(self._failures),
            opened_at=self._opened_at,
        )
        # Persist state asynchronously so we don't block
        with contextlib.suppress(Exception):
            await self._persist_state()

    async def _half_open_circuit(self) -> None:
        self._state = CircuitState.HALF_OPEN
        self._half_open_requests = self.config.half_open_max_requests
        import structlog

        log = structlog.get_logger("scraper.circuit_breaker")
        log.info("circuit.half_open", source=self.source)

    async def _close_circuit(self) -> None:
        self._state = CircuitState.CLOSED
        self._opened_at = None
        self._failures.clear()
        self._half_open_requests = 0
        import structlog

        log = structlog.get_logger("scraper.circuit_breaker")
        log.info("circuit.closed", source=self.source)

    def _cleanup_window(self) -> None:
        cutoff = time.time() - self.config.window_seconds
        self._failures = [t for t in self._failures if t > cutoff]

    async def _persist_state(self) -> None:
        try:
            state_key, failures_key, opened_key, client = await self._redis_key()
            await client.set(state_key, self._state.value, ex=86400)
            if self._opened_at:
                await client.set(opened_key, str(self._opened_at), ex=86400)
            # Replace failure list
            if self._failures:
                pipe = client.pipeline()
                pipe.delete(failures_key)
                pipe.rpush(failures_key, *[str(t) for t in self._failures])
                pipe.expire(failures_key, 86400)
                await pipe.execute()
            else:
                await client.delete(failures_key)
            await client.aclose()
        except Exception:
            pass


# Global registry of circuit breakers per source
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_lock = asyncio.Lock()


async def get_circuit_breaker(source: str) -> CircuitBreaker:
    """Get or create a CircuitBreaker for the given source."""
    async with _circuit_lock:
        if source not in _circuit_breakers:
            cb = CircuitBreaker(source=source)
            await cb._load_state()
            _circuit_breakers[source] = cb
        return _circuit_breakers[source]
