"""Browser connector using Chrome DevTools Protocol (CDP).

Connects to an existing Chrome browser session with authenticated social
accounts, enabling low-ban-rate scraping of social profiles.

Supports:
  - Persistent CDPBrowser connection reused across multiple scrapes
  - TabPool for concurrent tab management (each scrape gets its own tab)
  - TabContext for navigate-and-extract workflows

Usage:
    1. Start Chrome with: chrome --remote-debugging-port=9222 --user-data-dir="$HOME/.config/google-chrome"
    2. Log into desired social platforms in that Chrome session
    3. Use this module to crawl social profiles via the authenticated session
"""

from __future__ import annotations

import asyncio
import json
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

import httpx
import structlog

from leadforge_scraper_core.human_simulation import human_delay

logger = structlog.get_logger("scraper.browser_connector")

DEFAULT_CDP_URL = "http://localhost:9222"


@dataclass
class CDPBrowserConfig:
    cdp_url: str = DEFAULT_CDP_URL
    target_url: str | None = None
    navigation_timeout_ms: int = 30000
    idle_timeout_ms: int = 5000
    stealth: bool = True


@dataclass
class CDPTab:
    id: str
    url: str
    title: str
    type: str = "page"


class CDPBrowser:
    """Persistent Chrome DevTools Protocol connection.

    Creates one HTTP client + manages per-tab WebSocket connections.
    Reuse a single instance across multiple scrape operations.
    """

    def __init__(self, config: CDPBrowserConfig | None = None) -> None:
        self.config = config or CDPBrowserConfig()
        self._client: httpx.AsyncClient | None = None
        self._tab_websockets: dict[str, Any] = {}
        self._tab_message_ids: dict[str, int] = {}
        self._tab_responses: dict[str, dict[int, asyncio.Future]] = {}
        self._event_handlers: dict[str, list[callable]] = {}
        self._connected = False

    async def __aenter__(self) -> CDPBrowser:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.disconnect()

    # ── Connection ────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        if self._connected:
            return
        self._client = httpx.AsyncClient(timeout=30.0)
        self._connected = True
        logger.info("cdp.connecting", cdp_url=self.config.cdp_url)
        tabs = await self.list_tabs()
        if not tabs:
            raise RuntimeError(
                "No Chrome tabs found. Is Chrome running with --remote-debugging-port=9222?"
            )
        logger.info("cdp.connected", tabs_count=len(tabs))

    async def disconnect(self) -> None:
        for _tab_id, ws in list(self._tab_websockets.items()):
            with suppress(Exception):
                await ws.aclose()
        self._tab_websockets.clear()
        self._tab_message_ids.clear()
        self._tab_responses.clear()
        if self._client:
            await self._client.aclose()
            self._client = None
        self._connected = False
        logger.info("cdp.disconnected")

    async def list_tabs(self) -> list[CDPTab]:
        if not self._client:
            raise RuntimeError("Not connected. Call connect() first.")
        resp = await self._client.get(f"{self.config.cdp_url}/json")
        resp.raise_for_status()
        return [
            CDPTab(
                id=tab.get("id", ""),
                url=tab.get("url", ""),
                title=tab.get("title", ""),
                type=tab.get("type", "page"),
            )
            for tab in resp.json()
            if tab.get("type") == "page"
        ]

    async def get_active_tab(self) -> CDPTab | None:
        tabs = await self.list_tabs()
        for tab in tabs:
            if tab.url and not tab.url.startswith("chrome://"):
                return tab
        return tabs[0] if tabs else None

    # ── Tab Management ────────────────────────────────────────────────────────

    async def create_tab(self, url: str = "about:blank") -> CDPTab:
        """Open a new Chrome tab and return its info."""
        if not self._client:
            raise RuntimeError("Not connected")
        resp = await self._client.put(
            f"{self.config.cdp_url}/json/new",
            params={"url": url},
        )
        resp.raise_for_status()
        data = resp.json()
        return CDPTab(
            id=data.get("id", ""),
            url=data.get("url", ""),
            title=data.get("title", ""),
            type=data.get("type", "page"),
        )

    async def close_tab(self, tab_id: str) -> None:
        """Close a Chrome tab and clean up its WebSocket."""
        ws = self._tab_websockets.pop(tab_id, None)
        if ws:
            with suppress(Exception):
                await ws.aclose()
        self._tab_message_ids.pop(tab_id, None)
        self._tab_responses.pop(tab_id, None)
        if self._client:
            with suppress(Exception):
                await self._client.get(f"{self.config.cdp_url}/json/close/{tab_id}")

    # ── WebSocket per Tab ─────────────────────────────────────────────────────

    async def _get_tab_ws(self, tab_id: str) -> Any:
        """Get or create a persistent WebSocket for a specific tab."""
        if tab_id in self._tab_websockets:
            return self._tab_websockets[tab_id]

        ws_url = f"{self.config.cdp_url.replace('http', 'ws')}/devtools/page/{tab_id}"
        import websockets

        ws = await websockets.connect(ws_url)
        self._tab_websockets[tab_id] = ws
        self._tab_message_ids[tab_id] = 0
        self._tab_responses[tab_id] = {}
        return ws

    async def _send_to_tab(self, tab_id: str, method: str, params: dict | None = None) -> Any:
        """Send a CDP command to a specific tab via its WebSocket."""
        ws = await self._get_tab_ws(tab_id)
        msg_id = self._tab_message_ids[tab_id]
        self._tab_message_ids[tab_id] += 1

        payload: dict[str, Any] = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._tab_responses[tab_id][msg_id] = future
        await ws.send_text(json.dumps(payload))

        try:
            return await asyncio.wait_for(future, timeout=30.0)
        finally:
            self._tab_responses[tab_id].pop(msg_id, None)

    async def _handle_ws_messages(self, tab_id: str) -> None:
        """Background task to process incoming messages for a tab."""
        ws = self._tab_websockets.get(tab_id)
        if not ws:
            return
        try:
            async for raw in ws:
                msg = json.loads(raw)
                if "id" in msg:
                    future = self._tab_responses.get(tab_id, {}).get(msg["id"])
                    if future and not future.done():
                        if "error" in msg:
                            future.set_exception(
                                Exception(msg["error"].get("message", "CDP Error"))
                            )
                        else:
                            future.set_result(msg.get("result"))
                elif "method" in msg:
                    for handler in self._event_handlers.get(msg["method"], []):
                        try:
                            await handler(msg.get("params", {}))
                        except Exception as e:
                            logger.warning(
                                "cdp.event_handler_error", method=msg["method"], error=str(e)
                            )
        except Exception:
            pass

    # ── Stealth ───────────────────────────────────────────────────────────────

    async def _apply_stealth_to_tab(self, tab_id: str) -> None:
        evasions = [
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined, configurable: true})",
            """
            if (!window.chrome) window.chrome = {};
            if (!window.chrome.runtime) window.chrome.runtime = {};
            """,
        ]
        for evasion in evasions:
            with suppress(Exception):
                await self._send_to_tab(tab_id, "Runtime.evaluate", {"expression": evasion})

    # ── High-Level Tab Operations ─────────────────────────────────────────────

    async def navigate_tab(self, tab_id: str, url: str) -> str:
        """Navigate a tab to a URL. Returns final URL."""
        await self._send_to_tab(tab_id, "Page.enable")
        await self._send_to_tab(tab_id, "Page.navigate", {"url": url})

        # Wait for load
        with suppress(TimeoutError, Exception):
            await asyncio.wait_for(
                self._wait_for_event(
                    "Page.loadEventFired", timeout=self.config.navigation_timeout_ms / 1000
                ),
                timeout=self.config.navigation_timeout_ms / 1000,
            )

        if self.config.stealth:
            await self._apply_stealth_to_tab(tab_id)
        return url

    async def get_tab_html(self, tab_id: str) -> str:
        """Get the full HTML content of a tab."""
        result = await self._send_to_tab(tab_id, "DOM.getDocument", {"depth": 0})
        root = result.get("root", {})
        html_result = await self._send_to_tab(
            tab_id, "DOM.getOuterHTML", {"nodeId": root.get("nodeId", 0)}
        )
        return html_result.get("outerHTML", "")

    async def evaluate_in_tab(self, tab_id: str, expression: str) -> Any:
        """Run JavaScript in a tab and return the result."""
        result = await self._send_to_tab(
            tab_id,
            "Runtime.evaluate",
            {"expression": expression, "returnByValue": True},
        )
        return result.get("result", {}).get("value")

    @asynccontextmanager
    async def tab_context(self, url: str | None = None) -> AsyncIterator[TabContext]:
        """Create a temporary tab, navigate to URL, yield for scraping, then close."""
        tab = await self.create_tab(url or "about:blank")
        ctx = TabContext(self, tab.id)
        try:
            if url:
                await ctx.navigate(url)
            yield ctx
        finally:
            await self.close_tab(tab.id)

    # ── Event Handling ────────────────────────────────────────────────────────

    async def _wait_for_event(self, event_name: str, timeout: float = 30.0) -> Any:
        future: asyncio.Future = asyncio.get_event_loop().create_future()

        def handler(params: dict) -> None:
            if not future.done():
                future.set_result(params)

        self._event_handlers.setdefault(event_name, []).append(handler)
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._event_handlers[event_name] = [
                h for h in self._event_handlers[event_name] if h != handler
            ]

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    async def create(cls, **kwargs: Any) -> CDPBrowser:
        browser = cls(CDPBrowserConfig(**kwargs))
        await browser.connect()
        return browser


class TabContext:
    """Wrapper around a single Chrome tab for navigate-and-scrape workflows."""

    def __init__(self, browser: CDPBrowser, tab_id: str) -> None:
        self._browser = browser
        self.tab_id = tab_id

    async def navigate(self, url: str) -> str:
        return await self._browser.navigate_tab(self.tab_id, url)

    async def get_html(self) -> str:
        return await self._browser.get_tab_html(self.tab_id)

    async def evaluate(self, expression: str) -> Any:
        return await self._browser.evaluate_in_tab(self.tab_id, expression)

    async def navigate_and_get_html(self, url: str, delay_ms: int = 1500) -> str:
        """Navigate to URL, wait, extract HTML. One-call convenience."""
        await self.navigate(url)
        # Human-like delay for JS rendering
        jitter_ms = delay_ms + secrets.randbelow(max(1, delay_ms // 3)) - delay_ms // 6
        await asyncio.sleep(max(200, jitter_ms) / 1000.0)
        return await self.get_html()


# ── High-Level API (backward compatible) ──────────────────────────────────────


async def fetch_with_authenticated_session(
    url: str,
    cdp_url: str = DEFAULT_CDP_URL,
    stealth: bool = True,
) -> str | None:
    """Fetch a URL using an authenticated Chrome session (creates new connection)."""
    try:
        async with CDPBrowser.create(cdp_url=cdp_url, stealth=stealth) as browser:
            async with browser.tab_context(url) as tab:
                await human_delay(min_ms=1000, max_ms=3000)
                return await tab.get_html()
    except Exception as exc:
        logger.debug("fetch_auth_session.failed", url=url, error=str(exc))
        return None


async def scrape_social_profile(
    profile_url: str,
    platform: str,
    cdp_url: str = DEFAULT_CDP_URL,
    browser: CDPBrowser | None = None,
) -> dict[str, Any]:
    """Scrape a social profile for contact + rich data.

    If *browser* is provided, reuses its connection (preferred).
    Otherwise creates a temporary connection.
    """
    from leadforge_scraper_core.social import scrape_social_profile_rich

    own_browser = browser is None
    try:
        if own_browser:
            browser = await CDPBrowser.create(cdp_url=cdp_url)

        async with browser.tab_context(profile_url) as tab:
            await human_delay(min_ms=1500, max_ms=4000)
            html = await tab.get_html()

        if not html or len(html) < 200:
            return {}

        return await scrape_social_profile_rich(html, profile_url, platform)
    except Exception as exc:
        logger.debug("scrape_social_profile.failed", url=profile_url, error=str(exc))
        return {}
    finally:
        if own_browser and browser:
            await browser.disconnect()
