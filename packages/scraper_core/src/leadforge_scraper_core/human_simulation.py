"""Human-like browser simulation — mouse movements, scrolling, typing, timing.

Provides realistic interaction patterns so Playwright-based scraping is harder
to distinguish from real user traffic. All delays use cryptographically random
jitter within configurable bounds.

Designed for no-proxy mode (5–10 requests/hour) but equally useful with proxies.
"""

from __future__ import annotations

import asyncio
import math
import random
import secrets
import time
from typing import Any

from playwright.async_api import Page


# ── Timing ────────────────────────────────────────────────────────────────────

def jitter(base_ms: int = 1000, variance_ms: int = 500) -> float:
    """Return a random delay in *seconds* with crypto-strength jitter.

    Args:
        base_ms: Target delay in milliseconds.
        variance_ms: +/- jitter range in milliseconds.

    Returns:
        Delay in seconds (float).
    """
    ms = base_ms + secrets.randbelow(variance_ms * 2 + 1) - variance_ms
    return max(50, ms) / 1000.0


async def human_delay(
    min_ms: int = 500,
    max_ms: int = 2000,
    *,
    page: Page | None = None,
) -> None:
    """Sleep for a random human-like delay.

    If *page* is provided, also performs a tiny idle-mouse jitter to simulate
    a human who can't keep their mouse perfectly still.
    """
    delay = min_ms + secrets.randbelow(max_ms - min_ms + 1)
    await asyncio.sleep(delay / 1000.0)

    if page:
        try:
            # Use innerWidth/Height as reference and pick a random spot
            viewport = await page.evaluate(
                "() => ({w: window.innerWidth, h: window.innerHeight})"
            )
            cx = viewport["w"] // 2
            cy = viewport["h"] // 2
            dx = secrets.randbelow(11) - 5  # -5 to +5 px
            dy = secrets.randbelow(11) - 5
            await page.mouse.move(cx + dx, cy + dy, steps=2)
        except Exception:
            pass


# ── Mouse movements ───────────────────────────────────────────────────────────

def _bezier_path(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    steps: int = 20,
) -> list[tuple[float, float]]:
    """Generate a quadratic Bézier curve from start to end with a random control point.

    The control point is offset perpendicular to the direct line, creating a
    natural curved mouse path instead of a mechanical straight line.
    """
    dx = end_x - start_x
    dy = end_y - start_y

    # Control point offset (perpendicular + some forward)
    perp_x = -dy * 0.3 + secrets.randbelow(41) - 20
    perp_y = dx * 0.3 + secrets.randbelow(41) - 20
    ctrl_x = start_x + dx * 0.4 + perp_x
    ctrl_y = start_y + dy * 0.4 + perp_y

    points: list[tuple[float, float]] = []
    for i in range(steps):
        t = i / (steps - 1)
        # Quadratic Bézier: B(t) = (1-t)²·P₀ + 2(1-t)t·P₁ + t²·P₂
        x = (
            (1 - t) ** 2 * start_x
            + 2 * (1 - t) * t * ctrl_x
            + t ** 2 * end_x
        )
        y = (
            (1 - t) ** 2 * start_y
            + 2 * (1 - t) * t * ctrl_y
            + t ** 2 * end_y
        )
        # Add micro-jitter to each point (real mice don't follow perfect curves)
        points.append((
            x + secrets.randbelow(5) - 2,
            y + secrets.randbelow(5) - 2,
        ))
    return points


async def human_move_mouse(
    page: Page,
    end_x: float,
    end_y: float,
    *,
    start_x: float | None = None,
    start_y: float | None = None,
) -> None:
    """Move the mouse cursor along a human-like Bézier path.

    Args:
        page: Playwright page object.
        end_x, end_y: Target coordinates.
        start_x, start_y: Optional starting coordinates. If omitted, uses current
                          cursor position from the browser.
    """
    if start_x is None or start_y is None:
        pos = await page.evaluate(
            "() => ({x: window.mouseX || 0, y: window.mouseY || 0})"
        )
        start_x = pos["x"] or 300 + secrets.randbelow(401)
        start_y = pos["y"] or 200 + secrets.randbelow(301)

    steps = random.randint(15, 30)
    path = _bezier_path(start_x, start_y, end_x, end_y, steps)

    for px, py in path:
        await page.mouse.move(px, py)
        # Each step delay: 5–15ms (realistic mouse polling rate)
        await asyncio.sleep((5 + secrets.randbelow(11)) / 1000.0)


async def human_click(
    page: Page,
    end_x: float,
    end_y: float,
    *,
    button: str = "left",
) -> None:
    """Move the mouse to *end_x, end_y* with a human-like path, then click.

    Adds realistic pre-click hesitation (200–800ms) after reaching the target.
    """
    await human_move_mouse(page, end_x, end_y)
    await asyncio.sleep(jitter(400, 200))
    await page.mouse.click(end_x, end_y, button=button)


# ── Scrolling ─────────────────────────────────────────────────────────────────

async def human_scroll(
    page: Page,
    distance: int = 600,
    *,
    max_steps: int = 15,
    direction: str = "down",
) -> None:
    """Scroll the page in a human-like manner using variable-speed increments.

    Real humans accelerate, coast, then decelerate.  This mimics that by
    using a sine-curve velocity profile split across *max_steps*.

    Args:
        page: Playwright page object.
        distance: Total scroll distance in pixels (positive = down, negative = up).
        max_steps: Number of individual scroll wheel events.
        direction: "down" or "up".
    """
    sign = 1 if direction == "down" else -1
    total = abs(distance) * sign

    for i in range(max_steps):
        # Sine velocity profile: accelerate then decelerate
        progress = (i + 1) / max_steps
        velocity = math.sin(math.pi * progress)
        step = int(total * velocity / max_steps * (0.8 + secrets.randbelow(41) / 100.0))
        if step == 0:
            step = sign * random.randint(80, 150)

        await page.evaluate(f"window.scrollBy(0, {step})")
        await asyncio.sleep(jitter(80, 40))  # 40–120ms between scroll ticks

    # Small overshoot correction
    await asyncio.sleep(jitter(300, 100))


async def human_scroll_into_view(page: Page, selector: str) -> bool:
    """Scroll an element into view using natural scrolling, then hover near it.

    Returns True if the element was found and scrolled to.
    """
    try:
        el = await page.query_selector(selector)
        if not el:
            return False

        box = await el.bounding_box()
        if not box:
            return False

        # Scroll via JavaScript first (reliable), then hover naturally
        await el.scroll_into_view_if_needed()
        await asyncio.sleep(jitter(500, 250))

        # Hover near (but not exactly on) the element center
        target_x = box["x"] + box["width"] * (0.3 + secrets.randbelow(41) / 100.0)
        target_y = box["y"] + box["height"] * (0.3 + secrets.randbelow(41) / 100.0)
        await human_move_mouse(page, target_x, target_y)
        return True
    except Exception:
        return False


async def human_type(page: Page, text: str, *, selector: str | None = None) -> None:
    """Type text character by character with realistic inter-key delays.

    Args:
        page: Playwright page object.
        text: Text to type.
        selector: Optional CSS selector to focus first.
    """
    if selector:
        await page.click(selector)
        await asyncio.sleep(jitter(300, 150))

    for char in text:
        await page.keyboard.type(char)
        # Inter-key delay: 30–150ms (varies per character, slower after punctuation)
        base = 60 if char.isalpha() else 90
        variance = 60 if char.isalpha() else 90
        await asyncio.sleep(jitter(base, variance))


# ── Page interaction helpers ──────────────────────────────────────────────────

async def simulate_reading(page: Page, seconds: float) -> None:
    """Simulate a human reading a page — occasional tiny scrolls and idle mouse moves."""
    end_time = time.monotonic() + seconds
    while time.monotonic() < end_time:
        await asyncio.sleep(jitter(2000, 1000))

        # 30% chance of a tiny scroll
        if secrets.randbelow(100) < 30:
            await human_scroll(
                page, random.randint(50, 200), max_steps=random.randint(2, 5)
            )

        # 20% chance of moving the mouse
        if secrets.randbelow(100) < 20:
            try:
                viewport = await page.evaluate(
                    "() => ({w: window.innerWidth, h: window.innerHeight})"
                )
                await human_move_mouse(
                    page,
                    secrets.randbelow(viewport["w"]),
                    secrets.randbelow(viewport["h"]),
                )
            except Exception:
                pass


# ─── Convenience wrappers for common scraping patterns ────────────────────────

async def slowly_scroll_feed(page: Page, max_scrolls: int = 6) -> None:
    """Scroll a result feed (like Google Maps sidebar) in a human-like way.

    Each scroll is a different distance, with random pauses between scrolls
    as if the user is looking at results.
    """
    for _ in range(max_scrolls):
        await asyncio.sleep(jitter(1500, 700))
        scroll_dist = random.randint(300, 800)
        await human_scroll(page, scroll_dist, max_steps=random.randint(4, 8))


async def wait_and_click(
    page: Page,
    selector: str,
    *,
    timeout_ms: int = 5000,
) -> bool:
    """Wait for a selector to appear, then click it with human-like motion.

    Returns True if clicked successfully.
    """
    try:
        await page.wait_for_selector(selector, timeout=timeout_ms)
        el = await page.query_selector(selector)
        if not el:
            return False

        box = await el.bounding_box()
        if not box:
            return False

        # Target slightly off-center (real users don't click the exact center)
        target_x = box["x"] + box["width"] * (0.2 + secrets.randbelow(61) / 100.0)
        target_y = box["y"] + box["height"] * (0.2 + secrets.randbelow(61) / 100.0)
        await human_click(page, target_x, target_y)
        return True
    except Exception:
        return False
