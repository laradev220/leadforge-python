"""Enhanced base scraper utilities — retries, rate limiting, proxy rotation, caching.

This module replaces the original base.py. Key improvements:
  - asyncio.Semaphore for global concurrency
  - DomainRateLimiter for per-domain delays
  - tenacity-based retry with exponential backoff + jitter
  - Proxy rotation via ProxyManager
  - Redis HTML cache (24h TTL)
  - Structured logging with source, url, keyword, location, duration_ms, success, etc.
  - Custom exceptions (RateLimitError, ProxyError) for targeted handling
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx
from tenacity import (
    after_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)
from playwright.async_api import async_playwright

from leadforge_config import get_settings
from leadforge_scraper_core.exceptions import RateLimitError, ProxyError
from leadforge_scraper_core.monitors.rate_limiter import (
    GlobalConcurrencyLimiter,
    AdaptiveRateLimiter,
)
from leadforge_scraper_core.monitors.proxy_rotator import get_proxy_manager
from leadforge_scraper_core.cache import get_cache


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

# Global concurrency limiter
_global_limiter = GlobalConcurrencyLimiter()
_domain_limiter = AdaptiveRateLimiter(
    base_delay=get_settings().scraper_request_delay_ms / 1000.0,
    max_delay=60.0,
)


def _get_logger() -> Any:
    import structlog
    return structlog.get_logger("scraper.base")


def _is_retryable_exception(exc: Exception) -> bool:
    """Return True for errors that warrant a retry."""
    if isinstance(exc, (httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429, 500, 502, 503, 504)
    if isinstance(exc, RateLimitError):
        return True
    return False


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_html(
    url: str,
    use_playwright: bool = False,
    timeout_ms: int | None = None,
    *,
    keyword: str = "",
    location: str = "",
    source: str = "unknown",
    logger: Any = None,
    retry_count: int = 0,
) -> str | None:
    """Fetch HTML with retry, rate limiting, proxy rotation, and caching.

    Args:
        url: URL to fetch.
        use_playwright: Use Playwright instead of httpx.
        timeout_ms: Custom timeout override.
        keyword: Search keyword (for structured logging).
        location: Search location (for structured logging).
        source: Source name (for structured logging and metrics).
        logger: Optional structlog logger for this request.
        retry_count: Current retry number (incremented by tenacity).
    """
    from leadforge_scraper_core import metrics as scraper_metrics

    settings = get_settings()
    timeout = timeout_ms or settings.scraper_request_timeout_ms / 1000.0
    ua = random.choice(USER_AGENTS)

    log = logger or _get_logger()
    start_time = time.monotonic()

    # Enforce global concurrency
    async with _global_limiter:
        # Enforce per-domain rate limiting
        domain = _extract_domain(url)
        if domain:
            await _domain_limiter.acquire(domain)

        # Get proxy
        proxy_manager = get_proxy_manager()
        proxy = await proxy_manager.get_next()

        scraper_metrics.record_scrape_start(source)

        try:
            html = await _do_fetch(
                url,
                use_playwright=use_playwright,
                timeout=timeout,
                ua=ua,
                proxy=proxy,
                settings=settings,
                log=log,
            )
            duration_ms = int((time.monotonic() - start_time) * 1000)

            if html:
                # Check cache headers
                cache = get_cache()
                cached = await cache.get(url, ua)
                if cached:
                    scraper_metrics.record_cache_hit()
                else:
                    scraper_metrics.record_cache_miss()
                    await cache.set(url, ua, html)

                scraper_metrics.record_scrape_success(source, duration_ms)
                if proxy:
                    await proxy_manager.record_success(proxy)
                log.info(
                    "fetch.success",
                    source=source,
                    url=url,
                    keyword=keyword,
                    location=location,
                    duration_ms=duration_ms,
                    success=True,
                    retry_count=retry_count,
                    proxy_used=proxy,
                )
                return html
            else:
                scraper_metrics.record_scrape_failure(source, "empty_response", duration_ms)
                return None

        except RateLimitError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            scraper_metrics.record_scrape_failure(source, "rate_limit", duration_ms)
            if domain:
                await _domain_limiter.note_429(domain)
            log.warning(
                "fetch.rate_limited",
                source=source, url=url, keyword=keyword, location=location,
                duration_ms=duration_ms, success=False, retry_count=retry_count,
                proxy_used=proxy, error=str(exc),
            )
            raise

        except ProxyError as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            scraper_metrics.record_scrape_failure(source, "proxy_error", duration_ms)
            if proxy:
                scraper_metrics.record_proxy_failure(proxy)
                await proxy_manager.record_failure(proxy, exc)
            log.warning(
                "fetch.proxy_failed",
                source=source, url=url, keyword=keyword, location=location,
                duration_ms=duration_ms, success=False, retry_count=retry_count,
                proxy_used=proxy, error=str(exc),
            )
            raise

        except Exception as exc:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            scraper_metrics.record_scrape_failure(source, "other", duration_ms)
            log.error(
                "fetch.failed",
                source=source, url=url, keyword=keyword, location=location,
                duration_ms=duration_ms, success=False, retry_count=retry_count,
                proxy_used=proxy, error=str(exc),
            )
            raise


# ── Retry wrapper ─────────────────────────────────────────────────────────────

def retrying_fetch(*, source: str = "unknown", keyword: str = "", location: str = ""):
    """Decorator that wraps fetch_html with tenacity retry logic.

    Returns a callable that accepts the same arguments as fetch_html.
    """
    log = _get_logger()

    def wrapper(
        url: str,
        use_playwright: bool = False,
        timeout_ms: int | None = None,
        *,
        logger: Any = None,
    ):
        from tenacity import retry

        r = retry(
            stop=stop_after_attempt(3),
            wait=wait_exponential_jitter(initial=1, max=10, jitter=2),
            retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError, RateLimitError)),
            after=after_log(log, logging.WARNING),
            reraise=True,
        )

        async def _retry_fn():
            return await fetch_html(
                url,
                use_playwright=use_playwright,
                timeout_ms=timeout_ms,
                keyword=keyword,
                location=location,
                source=source,
                logger=logger,
            )

        return r(_retry_fn)

    return wrapper


# ── Internal helpers ──────────────────────────────────────────────────────────

async def _do_fetch(
    url: str,
    *,
    use_playwright: bool,
    timeout: float,
    ua: str,
    proxy: str | None,
    settings: Any,
    log: Any,
) -> str | None:
    """Perform the actual HTTP fetch with optional Playwright."""
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    if not use_playwright:
        client_kwargs: dict[str, Any] = {"timeout": timeout, "follow_redirects": True, "headers": headers}
        if proxy:
            client_kwargs["proxy"] = proxy
        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(url)
                if response.status_code == 429:
                    raise RateLimitError("429 received", source="httpx", url=url)
                if response.status_code >= 500:
                    raise RateLimitError(f"HTTP {response.status_code}", source="httpx", url=url)
                # Accept 200 OR 403 (CDN/WAF block pages may have useful content)
                if response.status_code in (200, 403):
                    html = response.text
                    if len(html) > 500 and "cf-browser-verification" not in html and "captcha" not in html.lower():
                        return html
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise RateLimitError("429 received", source="httpx", url=url)
            raise
        except Exception as exc:
            if not _is_retryable_exception(exc):
                raise
            raise

    # Fall back to Playwright with stealth techniques
    try:
        async with async_playwright() as p:
            launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
            browser = await p.chromium.launch(
                headless=settings.playwright_headless,
                args=launch_args,
            )
            context_options: dict[str, Any] = {
                "user_agent": ua,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
                "extra_http_headers": {"Accept-Language": "en-US,en;q=0.9"},
            }
            # Apply proxy if available
            if proxy:
                context_options["proxy"] = {"server": proxy}  # type: ignore[assignment]

            context = await browser.new_context(**context_options)
            page = await context.new_page()

            # Stealth: override webdriver detection signals
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                window.chrome = { runtime: {} };
            """)

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
                content = await page.content()
                return content
            finally:
                await browser.close()
    except Exception as exc:
        if "timeout" in str(exc).lower():
            raise
        # Not wrapping in ProxyError — proxy is optional, this is a generic fetch failure
        raise


def _extract_domain(url: str) -> str:
    """Extract domain from URL for rate limiting."""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.removeprefix("www.")
    except Exception:
        return ""