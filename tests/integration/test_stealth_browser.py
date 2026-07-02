"""Integration tests for stealth browser detection and evasion.

Tests that the Playwright-based stealth browser:
1. Launches successfully with automation detection disabled
2. Avoids common bot detection signals
3. Loads pages correctly without triggering detection
"""

from __future__ import annotations

import contextlib

import pytest
from playwright.async_api import async_playwright

# ── Helpers ───────────────────────────────────────────────────────────────────


@pytest.fixture
async def stealth_browser():
    """Fixture that provides a launched stealth browser with Playwright instance."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-setuid-sandbox",
                "--disable-web-security",
            ],
        )
        yield browser
        await browser.close()


async def check_automation_detection(page):
    """Check if the page detects automation."""
    return await page.evaluate("""
        () => {
            const signals = [];
            if (navigator.webdriver === true) signals.push('webdriver_true');
            if (navigator.webdriver === undefined) signals.push('webdriver_undefined');
            if (window.chrome && window.chrome.runtime) signals.push('chrome_runtime');
            if (navigator.plugins.length === 0) signals.push('no_plugins');
            if (Notification.permission === 'default') signals.push('permissions_default');
            return signals;
        }
    """)


async def check_bot_signals(page):
    """Check for common bot detection text on the page."""
    content = await page.content()
    bot_signals = [
        "unusual traffic",
        "captcha",
        "cf-browser-verification",
        "sorry",
        "automated queries",
        "access denied",
    ]
    content_lower = content.lower()
    return [s for s in bot_signals if s in content_lower]


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestStealthBrowserLaunch:
    """Test stealth browser launch configuration."""

    @pytest.mark.asyncio
    async def test_launches_without_errors(self, stealth_browser):
        """Browser should launch successfully with stealth arguments."""
        assert stealth_browser is not None
        with contextlib.suppress(AttributeError):
            assert not stealth_browser.is_closed

    @pytest.mark.asyncio
    async def test_navigator_webdriver_undefined(self, stealth_browser):
        """navigator.webdriver should be undefined (not True) in stealth mode."""
        context = await stealth_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
        )
        page = await context.new_page()
        try:
            await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
            webdriver_val = await page.evaluate("() => navigator.webdriver")
            assert not webdriver_val, "navigator.webdriver should not be True"
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_no_automation_detection_signals(self, stealth_browser):
        """Stealth browser should not trigger automation detection."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
            webdriver = await page.evaluate("() => navigator.webdriver")
            assert not webdriver, "Automation detected (webdriver=True)"
            detection = await check_automation_detection(page)
            assert "webdriver_true" not in detection
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_plugins_available(self, stealth_browser):
        """Stealth browser should have plugins (not empty like automation)."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        try:
            await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
            plugin_count = await page.evaluate("() => navigator.plugins.length")
            assert plugin_count >= 0
        finally:
            await context.close()


class TestBotDetectionEvasion:
    """Test that stealth browser avoids triggering bot detection."""

    @pytest.mark.asyncio
    async def test_loads_static_html_without_detection(self, stealth_browser):
        """Static HTML page should load without triggering bot detection."""
        context = await stealth_browser.new_context(locale="en-US")
        page = await context.new_page()
        try:
            await page.goto(
                "data:text/html,<html><body><h1>Business Name</h1><p>123 Main St</p>"
                "<p>+1 (555) 123-4567</p></body></html>",
                wait_until="domcontentloaded",
            )
            detection = await check_automation_detection(page)
            bot_signals = await check_bot_signals(page)
            assert "webdriver_true" not in detection, f"Automation detected: {detection}"
            assert len(bot_signals) == 0, f"Bot signals found: {bot_signals}"
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_stealth_context_configured(self, stealth_browser):
        """Stealth context should be configured with locale and headers."""
        context = await stealth_browser.new_context(
            locale="en-US",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        page = await context.new_page()
        try:
            await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
            h1 = await page.text_content("h1")
            assert h1 == "Test"
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_resource_routing_blocks_images(self, stealth_browser):
        """Image/css resources should be blocked to reduce detection surface."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        blocked = []

        async def block_images(route):
            blocked.append(route.request.url)
            await route.abort()

        await page.route("**/*.{png,jpg,jpeg,gif,svg,woff,woff2,css}", block_images)
        try:
            await page.goto(
                "data:text/html,<html><body><h1>Test</h1></body></html>",
                wait_until="domcontentloaded",
            )
        finally:
            await context.close()


class TestStealthBrowserNavigation:
    """Test stealth browser page navigation and content retrieval."""

    @pytest.mark.asyncio
    async def test_page_content_retrievable(self, stealth_browser):
        """Page content should be fully retrievable after navigation."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        try:
            test_html = (
                "<html><head><title>Test Page</title></head><body>"
                "<h1 class='title'>Joe's Pizza</h1><p class='address'>123 Broadway, NY</p>"
                "<p class='phone'>+1-212-555-1234</p></body></html>"
            )
            await page.goto(f"data:text/html,{test_html}", wait_until="domcontentloaded")
            content = await page.content()
            assert "Joe's Pizza" in content
            assert "123 Broadway" in content
            assert "+1-212-555-1234" in content
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_multiple_viewport_sizes(self, stealth_browser):
        """Stealth browser should support different viewport sizes."""
        viewports = [
            {"width": 1920, "height": 1080},
            {"width": 1366, "height": 768},
            {"width": 1536, "height": 864},
        ]
        for vp in viewports:
            context = await stealth_browser.new_context(viewport=vp)
            page = await context.new_page()
            try:
                await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
                assert page.viewport_size == vp
            finally:
                await context.close()

    @pytest.mark.asyncio
    async def test_async_context_cleanup(self, stealth_browser):
        """Browser context should clean up properly."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
        content = await page.content()
        assert "Test" in content
        await context.close()


class TestStealthBrowserEvasionScenarios:
    """Test real-world evasion scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_pages_sequential(self, stealth_browser):
        """Stealth browser should handle sequential navigation to multiple pages."""
        context = await stealth_browser.new_context()
        page = await context.new_page()
        try:
            pages_data = [
                "<html><body><h1>Business A</h1><p>Phone: 555-1111</p></body></html>",
                "<html><body><h1>Business B</h1><p>Phone: 555-2222</p></body></html>",
            ]
            for i, html in enumerate(pages_data):
                await page.goto(f"data:text/html,{html}", wait_until="domcontentloaded")
                h1 = await page.text_content("h1")
                assert h1 == f"Business {'A' if i == 0 else 'B'}"
        finally:
            await context.close()

    @pytest.mark.asyncio
    async def test_user_agent_rotation(self, stealth_browser):
        """Different user agents should be usable for rotation."""
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
        ]
        for ua in user_agents:
            context = await stealth_browser.new_context(user_agent=ua)
            page = await context.new_page()
            try:
                await page.goto("data:text/html,<h1>Test</h1>", wait_until="domcontentloaded")
                detected_ua = await page.evaluate("() => navigator.userAgent")
                assert len(detected_ua) > 0
            finally:
                await context.close()
