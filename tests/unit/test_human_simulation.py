"""Unit tests for human_simulation module — jitter, Bézier paths, scrolling helpers.

Most functions require a Playwright Page object, so we test the pure functions
directly and use Mock for the Page-dependent ones.
"""

from __future__ import annotations

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Lazy import — the module depends on playwright.async_api which may not be
# installed in all test environments.
pytest.importorskip("playwright")

from leadforge_scraper_core.human_simulation import (
    jitter,
    human_delay,
    _bezier_path,
    human_move_mouse,
    human_click,
    human_scroll,
    human_scroll_into_view,
    human_type,
    simulate_reading,
    slowly_scroll_feed,
    wait_and_click,
)


# ── jitter ────────────────────────────────────────────────────────────────────

class TestJitter:
    """Tests for the jitter() timing function."""

    def test_returns_float(self) -> None:
        result = jitter(1000, 500)
        assert isinstance(result, float)

    def test_within_bounds(self) -> None:
        for _ in range(100):
            result = jitter(1000, 500)
            assert 0.05 <= result <= 1.5  # min 50ms, max 1500ms

    def test_exact_base(self) -> None:
        result = jitter(500, 0)
        assert result == 0.5  # 500ms → 0.5s

    def test_minimum_floor(self) -> None:
        """jitter should never return less than 50ms (0.05s)."""
        for _ in range(50):
            result = jitter(10, 20)
            assert result >= 0.05

    def test_is_deterministically_random(self) -> None:
        """Multiple calls should produce different values."""
        results = {jitter(500, 200) for _ in range(20)}
        assert len(results) > 1

    def test_variance_zero(self) -> None:
        """With variance=0, result should always be base_ms / 1000."""
        for _ in range(20):
            result = jitter(1000, 0)
            assert result == 1.0

    def test_typical_usage_range(self) -> None:
        """Typical jitter(400, 200) → 0.2s to 0.6s."""
        for _ in range(50):
            result = jitter(400, 200)
            assert 0.2 <= result <= 0.6


# ── _bezier_path ──────────────────────────────────────────────────────────────

class TestBezierPath:
    """Tests for the _bezier_path() pure function."""

    def test_returns_list_of_tuples(self) -> None:
        path = _bezier_path(0, 0, 100, 100, steps=20)
        assert isinstance(path, list)
        assert all(isinstance(p, tuple) and len(p) == 2 for p in path)

    def test_expected_number_of_points(self) -> None:
        path = _bezier_path(0, 0, 100, 100, steps=30)
        assert len(path) == 30

    def test_starts_at_origin(self) -> None:
        path = _bezier_path(10, 20, 100, 200, steps=20)
        # First point should be very close to start (within jitter)
        sx, sy = path[0]
        assert abs(sx - 10) <= 3
        assert abs(sy - 20) <= 3

    def test_ends_at_target(self) -> None:
        path = _bezier_path(10, 20, 100, 200, steps=20)
        # Last point should be very close to end (within jitter)
        ex, ey = path[-1]
        assert abs(ex - 100) <= 3
        assert abs(ey - 200) <= 3

    def test_monotonic_for_straight_line(self) -> None:
        """For a purely horizontal move, x should increase monotonically."""
        path = _bezier_path(0, 50, 200, 50, steps=30)
        xs = [p[0] for p in path]
        # Check that x is generally increasing (jitter may cause minor dips)
        assert xs[0] < xs[-1]
        assert all(0 <= x <= 203 for x in xs)

    def test_min_steps(self) -> None:
        path = _bezier_path(0, 0, 10, 10, steps=2)
        assert len(path) == 2

    def test_varied_start_and_end(self) -> None:
        path = _bezier_path(300, 400, 800, 200, steps=25)
        assert len(path) == 25
        # Check general direction
        sx, sy = path[0]
        ex, ey = path[-1]
        assert ex > sx  # x increased
        assert ey < sy  # y decreased (moved up)


# ── human_delay ───────────────────────────────────────────────────────────────

class TestHumanDelay:
    """Tests for human_delay() - timing only (page param tested with mock)."""

    @pytest.mark.asyncio
    async def test_minimum_delay(self) -> None:
        """Should wait at least min_ms."""
        start = asyncio.get_event_loop().time()
        await human_delay(50, 100)  # Fast minimum for testing
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04  # At least 40ms (margin for precision)

    @pytest.mark.asyncio
    async def test_delay_bounded(self) -> None:
        """Should not wait significantly longer than max_ms."""
        start = asyncio.get_event_loop().time()
        await human_delay(10, 50)  # Very short bounds
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 0.3  # Well within bounds (50ms + margin)

    @pytest.mark.asyncio
    async def test_with_page_no_error(self) -> None:
        """Should not raise when page is provided."""
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={"w": 1920, "h": 1080})
        mock_page.mouse.move = AsyncMock()
        await human_delay(10, 20, page=mock_page)
        mock_page.evaluate.assert_called_once()
        mock_page.mouse.move.assert_called_once()

    @pytest.mark.asyncio
    async def test_page_evaluate_failure_handled(self) -> None:
        """Should handle page.evaluate failure gracefully."""
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(side_effect=Exception("eval failed"))
        # Should not raise
        await human_delay(10, 20, page=mock_page)


# ── human_move_mouse ──────────────────────────────────────────────────────────

class TestHumanMoveMouse:
    """Tests for human_move_mouse() with mocked Page."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        page = MagicMock()
        page.evaluate = AsyncMock(return_value={"x": 100, "y": 100})
        page.mouse.move = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_moves_mouse(self, mock_page: MagicMock) -> None:
        await human_move_mouse(mock_page, 500, 300, start_x=100, start_y=100)
        # Should have called mouse.move multiple times (path steps)
        assert mock_page.mouse.move.call_count >= 15

    @pytest.mark.asyncio
    async def test_calls_with_start_coords(self, mock_page: MagicMock) -> None:
        await human_move_mouse(mock_page, 500, 300, start_x=200, start_y=200)
        # First move should be near start
        first_call = mock_page.mouse.move.call_args_list[0]
        args, _ = first_call
        assert abs(args[0] - 200) <= 3
        assert abs(args[1] - 200) <= 3

    @pytest.mark.asyncio
    async def test_fetches_position_when_not_provided(self, mock_page: MagicMock) -> None:
        await human_move_mouse(mock_page, 500, 300)
        mock_page.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_ends_at_target(self, mock_page: MagicMock) -> None:
        await human_move_mouse(mock_page, 800, 600, start_x=100, start_y=100)
        last_call = mock_page.mouse.move.call_args_list[-1]
        args, _ = last_call
        assert abs(args[0] - 800) <= 3
        assert abs(args[1] - 600) <= 3


# ── human_click ───────────────────────────────────────────────────────────────

class TestHumanClick:
    """Tests for human_click() with mocked Page."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        page = MagicMock()
        page.evaluate = AsyncMock(return_value={"x": 100, "y": 100})
        page.mouse.move = AsyncMock()
        page.mouse.click = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_moves_then_clicks(self, mock_page: MagicMock) -> None:
        await human_click(mock_page, 400, 250)
        # Should have moved the mouse
        assert mock_page.mouse.move.call_count > 0
        # Should have clicked at target
        mock_page.mouse.click.assert_called_once_with(400, 250, button="left")

    @pytest.mark.asyncio
    async def test_right_click(self, mock_page: MagicMock) -> None:
        await human_click(mock_page, 400, 250, button="right")
        mock_page.mouse.click.assert_called_once_with(400, 250, button="right")


# ── human_scroll ──────────────────────────────────────────────────────────────

class TestHumanScroll:
    """Tests for human_scroll() with mocked Page."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        page = MagicMock()
        page.evaluate = AsyncMock(return_value=None)
        return page

    @pytest.mark.asyncio
    async def test_scrolls_page(self, mock_page: MagicMock) -> None:
        await human_scroll(mock_page, 500, max_steps=5, direction="down")
        # Should have called window.scrollBy multiple times
        assert mock_page.evaluate.call_count >= 5

    @pytest.mark.asyncio
    async def test_scrolls_up(self, mock_page: MagicMock) -> None:
        import re
        await human_scroll(mock_page, 300, max_steps=4, direction="up")
        # All scrollBy calls should contain a negative y value
        for call_args in mock_page.evaluate.call_args_list:
            script = call_args[0][0]
            if "scrollBy" in script:
                match = re.search(r"scrollBy\(0,\s*(-?\d+)\)", script)
                assert match is not None, f"Could not parse scroll value from: {script}"
                value = int(match.group(1))
                assert value < 0, f"Scroll value {value} should be negative"

    @pytest.mark.asyncio
    async def test_min_steps(self, mock_page: MagicMock) -> None:
        await human_scroll(mock_page, 200, max_steps=2)
        assert mock_page.evaluate.call_count >= 2


# ── human_scroll_into_view ────────────────────────────────────────────────────

class TestHumanScrollIntoView:
    """Tests for human_scroll_into_view() with mocked Page."""

    @pytest.fixture
    def mock_element(self) -> MagicMock:
        el = MagicMock()
        el.bounding_box = AsyncMock(
            return_value={"x": 100, "y": 200, "width": 300, "height": 50}
        )
        el.scroll_into_view_if_needed = AsyncMock()
        return el

    @pytest.fixture
    def mock_page(self, mock_element: MagicMock) -> MagicMock:
        page = MagicMock()
        page.query_selector = AsyncMock(return_value=mock_element)
        page.evaluate = AsyncMock(return_value={"x": 500, "y": 300})
        page.mouse.move = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self, mock_page: MagicMock) -> None:
        result = await human_scroll_into_view(mock_page, ".result")
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_no_element(self, mock_page: MagicMock) -> None:
        mock_page.query_selector = AsyncMock(return_value=None)
        result = await human_scroll_into_view(mock_page, ".missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_handles_exception(self, mock_page: MagicMock) -> None:
        mock_page.query_selector = AsyncMock(side_effect=Exception("fail"))
        result = await human_scroll_into_view(mock_page, ".result")
        assert result is False


# ── human_type ────────────────────────────────────────────────────────────────

class TestHumanType:
    """Tests for human_type() with mocked Page."""

    @pytest.fixture
    def mock_page(self) -> MagicMock:
        page = MagicMock()
        page.click = AsyncMock()
        page.keyboard.type = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_types_characters(self, mock_page: MagicMock) -> None:
        await human_type(mock_page, "hello", selector="#input")
        mock_page.click.assert_called_once_with("#input")
        # Should type each character
        assert mock_page.keyboard.type.call_count == 5

    @pytest.mark.asyncio
    async def test_type_without_selector(self, mock_page: MagicMock) -> None:
        await human_type(mock_page, "hi")
        mock_page.click.assert_not_called()
        assert mock_page.keyboard.type.call_count == 2


# ── simulate_reading ──────────────────────────────────────────────────────────

class TestSimulateReading:
    """Tests for simulate_reading() with mocked Page."""

    @pytest.mark.asyncio
    async def test_runs_for_duration(self) -> None:
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value={"w": 1920, "h": 1080})
        mock_page.mouse.move = AsyncMock()

        start = asyncio.get_event_loop().time()
        await simulate_reading(mock_page, 0.05)  # Very short duration
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed >= 0.04


# ── slowly_scroll_feed ────────────────────────────────────────────────────────

class TestSlowlyScrollFeed:
    """Tests for slowly_scroll_feed() with mocked Page."""

    @pytest.mark.asyncio
    async def test_scrolls_specified_times(self) -> None:
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value=None)

        await slowly_scroll_feed(mock_page, max_scrolls=2)
        # Should have scrolled at least 2 times (min 1 call per scroll + delay sleeps)
        assert mock_page.evaluate.call_count >= 2

    @pytest.mark.asyncio
    async def test_default_max_scrolls(self) -> None:
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value=None)

        await slowly_scroll_feed(mock_page)
        assert mock_page.evaluate.call_count >= 2  # At least 2 scrolls


# ── wait_and_click ────────────────────────────────────────────────────────────

class TestWaitAndClick:
    """Tests for wait_and_click() with mocked Page."""

    @pytest.fixture
    def mock_element(self) -> MagicMock:
        el = MagicMock()
        el.bounding_box = AsyncMock(
            return_value={"x": 100, "y": 200, "width": 100, "height": 40}
        )
        return el

    @pytest.fixture
    def mock_page(self, mock_element: MagicMock) -> MagicMock:
        page = MagicMock()
        page.wait_for_selector = AsyncMock(return_value=mock_element)
        page.query_selector = AsyncMock(return_value=mock_element)
        page.evaluate = AsyncMock(return_value={"x": 100, "y": 100})
        page.mouse.move = AsyncMock()
        page.mouse.click = AsyncMock()
        return page

    @pytest.mark.asyncio
    async def test_clicks_element(self, mock_page: MagicMock) -> None:
        result = await wait_and_click(mock_page, ".btn")
        assert result is True
        mock_page.mouse.click.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_no_element(self) -> None:
        """Should return False when element is not found."""
        mock_page = MagicMock()
        mock_page.wait_for_selector = AsyncMock(return_value=None)
        mock_page.query_selector = AsyncMock(return_value=None)
        result = await wait_and_click(mock_page, ".missing")
        assert result is False

    @pytest.mark.asyncio
    async def test_handles_timeout(self) -> None:
        mock_page = MagicMock()
        mock_page.wait_for_selector = AsyncMock(
            side_effect=Exception("timeout")
        )
        result = await wait_and_click(mock_page, ".btn")
        assert result is False
