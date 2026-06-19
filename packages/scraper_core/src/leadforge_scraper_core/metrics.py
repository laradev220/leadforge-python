"""Prometheus metrics and scraper health endpoint.

Exports metrics for:
  - scrape_requests_total{source, status}
  - scrape_failures_total{source, reason}
  - scrape_success_rate{source}
  - cache_hit_rate
  - proxy_failures_total{proxy}
  - selector_failures_total{source, selector}
  - circuit_breaker_state{source}
"""

from __future__ import annotations

from typing import Any

from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST

from leadforge_scraper_core.monitors.circuit_breaker import CircuitState


# ── Counters ─────────────────────────────────────────────────────────────────

scrape_requests_total = Counter(
    "scrape_requests_total",
    "Total scrape requests",
    ["source", "status"],
)

scrape_failures_total = Counter(
    "scrape_failures_total",
    "Total scrape failures",
    ["source", "reason"],
)

proxy_failures_total = Counter(
    "proxy_failures_total",
    "Total proxy failures",
    ["proxy"],
)

selector_failures_total = Counter(
    "selector_failures_total",
    "Total selector failures",
    ["source", "selector"],
)

ai_fallback_total = Counter(
    "ai_fallback_total",
    "Total AI fallback invocations",
    [],
)

# ── Gauges ───────────────────────────────────────────────────────────────────

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    "Circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["source"],
)

cache_hit_total = Counter("cache_hit_total", "Total cache hits", [])
cache_miss_total = Counter("cache_miss_total", "Total cache misses", [])

# ── Histograms ───────────────────────────────────────────────────────────────

scrape_duration_seconds = Histogram(
    "scrape_duration_seconds",
    "Scrape request duration in seconds",
    ["source"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

retry_count = Histogram(
    "scrape_retry_count",
    "Number of retries per scrape request",
    ["source"],
    buckets=(0, 1, 2, 3),
)


# ── Rate computation helpers ──────────────────────────────────────────────────

def scrape_success_rate(source: str) -> float:
    """Compute success rate as a ratio from counter values."""
    # Note: in multi-process Prometheus, use reduce_labels for accuracy
    # Here we provide a helper that can be called by the health endpoint
    return 0.0  # Placeholder — actual computation done at scrape time


def record_scrape_start(source: str) -> None:
    scrape_requests_total.labels(source=source, status="started").inc()


def record_scrape_success(source: str, duration_ms: float) -> None:
    scrape_requests_total.labels(source=source, status="success").inc()
    scrape_duration_seconds.labels(source=source).observe(duration_ms / 1000)


def record_scrape_failure(source: str, reason: str, duration_ms: float) -> None:
    scrape_requests_total.labels(source=source, status="failure").inc()
    scrape_failures_total.labels(source=source, reason=reason).inc()
    scrape_duration_seconds.labels(source=source).observe(duration_ms / 1000)


def record_cache_hit() -> None:
    cache_hit_total.inc()


def record_cache_miss() -> None:
    cache_miss_total.inc()


def record_selector_failure(source: str, selector: str) -> None:
    selector_failures_total.labels(source=source, selector=selector).inc()


def record_proxy_failure(proxy: str) -> None:
    proxy_failures_total.labels(proxy=proxy[:32]).inc()


def set_circuit_state(source: str, state: CircuitState) -> None:
    state_map = {CircuitState.CLOSED: 0, CircuitState.HALF_OPEN: 1, CircuitState.OPEN: 2}
    circuit_breaker_state.labels(source=source).set(state_map.get(state, 0))


def get_metrics_bytes() -> bytes:
    return generate_latest()


def get_metrics_content_type() -> str:
    return CONTENT_TYPE_LATEST


# ── Health endpoint data ─────────────────────────────────────────────────────

async def get_scraper_health() -> dict[str, Any]:
    """Gather health status for all known scraper sources."""
    from leadforge_scraper_core.monitors.circuit_breaker import _circuit_breakers

    health: dict[str, Any] = {}
    for source, cb in _circuit_breakers.items():
        health[source] = {
            "circuit_state": cb.state.value,
            "failure_rate": cb.failure_rate,
            "recent_failures": len(cb._failures),
            "opened_at": cb._opened_at,
        }
    return health