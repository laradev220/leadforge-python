"""Regression tests for selectors.yaml parsing.

The YAML uses ``- css: "..."`` / ``- xpath: "..."`` entries; the strategy used
to read ``{"type": ..., "selector": ...}`` and therefore always extracted with
an empty selector ("Can't parse CSS selector.").
"""

from __future__ import annotations

from leadforge_scraper_core.strategies.selector import SelectorStrategy

HTML = (
    '<div class="result"><h2 class="title">Acme Dental</h2>'
    '<span class="phone">+92 300 1234567</span></div>'
)


def _strategy(field_selectors: dict) -> SelectorStrategy:
    strategy = SelectorStrategy()
    strategy._config = {"sources": {"example": field_selectors}}
    return strategy


async def test_css_entries_are_parsed() -> None:
    strategy = _strategy({"name": [{"css": "h2.title"}], "phone": [{"css": ".phone"}]})
    result = await strategy.extract(HTML, "https://example.com/search")

    assert result is not None
    assert result.name == "Acme Dental"
    assert result.phone is not None
    assert result.phone.startswith("+92")


async def test_xpath_entries_are_parsed() -> None:
    strategy = _strategy({"name": [{"xpath": "//h2[@class='title']"}]})
    result = await strategy.extract(HTML, "https://example.com/search")

    assert result is not None
    assert result.name == "Acme Dental"


async def test_unknown_source_returns_none() -> None:
    strategy = SelectorStrategy()
    strategy._config = {"sources": {}}
    assert await strategy.extract(HTML, "https://unmapped.test/search") is None
