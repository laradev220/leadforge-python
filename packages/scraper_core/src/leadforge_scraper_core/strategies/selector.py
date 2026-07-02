"""SelectorStrategy — uses a per-site YAML configuration with multiple fallback selectors.

If a selector fails (returns empty), the next one is tried.  All failures are
reported to the SelectorTracker so degraded selectors are detected automatically.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from selectolax.parser import HTMLParser

from leadforge_scraper_core.strategies.base import (
    ExtractionStrategy,
    StrategyResult,
)


class SelectorStrategy(ExtractionStrategy):
    """Extract using per-site selector configuration from selectors.yaml."""

    name = "selector"
    priority = 10

    # Path to the bundled selectors config (resolved relative to this file)
    _SELECTORS_PATH = Path(__file__).parent.parent / "selectors.yaml"

    def __init__(self) -> None:
        self._config: dict[str, Any] | None = None

    @property
    def config(self) -> dict[str, Any]:
        """Lazy-load the selectors.yaml config."""
        if self._config is None:
            self._config = self._load_config()
        return self._config

    def _load_config(self) -> dict[str, Any]:
        """Load selectors.yaml from disk, falling back to bundled file."""
        path = os.environ.get("SELECTORS_CONFIG_PATH", str(self._SELECTORS_PATH))
        try:
            with open(path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            # Try bundled
            try:
                with open(self._SELECTORS_PATH, encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            except FileNotFoundError:
                return {"sources": {}}

    def _get_source_key(self, url: str) -> str:
        """Infer the source key from the URL hostname."""
        try:
            from urllib.parse import urlparse

            host = urlparse(url).netloc.removeprefix("www.")
        except Exception:
            host = ""
        # Map known hosts to config keys
        host_to_key = {
            "yelp.com": "yelp",
            "yellowpages.com.pk": "yellowpages_pk",
            "hotfrog.pk": "hotfrog_pk",
            "cybo.com": "cybo_pk",
            "kompass.com": "kompass_pk",
            "yell.com": "yell_uk",
            "google.com": "google_maps",
        }
        for pattern, key in host_to_key.items():
            if pattern in host:
                return key
        # Fall back to searching all keys
        for key in self.config.get("sources", {}):
            if key.replace("_", "") in host.replace(".", ""):
                return key
        return ""

    def can_handle(self, html: str) -> bool:
        # Selector strategy is always applicable
        return True

    async def extract(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
        tracker: Any = None,
    ) -> StrategyResult | None:
        """Extract using the first working selector from the YAML config."""
        source_key = self._get_source_key(url)
        if not source_key or source_key not in self.config.get("sources", {}):
            if logger:
                logger.debug("selector_strategy.skip_no_config", url=url, source_key=source_key)
            return None

        tree = HTMLParser(html)
        field_selectors = self.config["sources"][source_key]

        result = StrategyResult(strategy_name=self.name)
        made_extraction = False

        for field, selectors in field_selectors.items():
            value = None
            failed_selectors = []

            for sel_spec in selectors:
                sel_type = "css"  # default
                sel = sel_spec
                if isinstance(sel_spec, dict):
                    sel_type = sel_spec.get("type", "css")
                    sel = sel_spec.get("selector", "")

                try:
                    if sel_type == "xpath":
                        value = self._xpath_extract(tree, sel)
                    else:
                        value = self._css_extract(tree, sel)
                    if value:
                        break
                except Exception as exc:
                    if logger:
                        logger.debug(
                            "selector.failed",
                            source=source_key,
                            field=field,
                            selector=sel,
                            error=str(exc),
                        )
                    failed_selectors.append(sel)

            # Report failures to tracker
            if not value and failed_selectors and tracker:
                for sel in failed_selectors:
                    await tracker.record_failure(source_key, field, sel, url=url)

            if value:
                made_extraction = True
                self._apply_field(result, field, value)

        if made_extraction:
            result.confidence = 80
            return result
        return None

    def _css_extract(self, tree: HTMLParser, selector: str) -> str | None:
        """Return text content of first CSS match."""
        node = tree.css_first(selector)
        if node is None:
            return None
        text = node.text(strip=True)
        return text if text else None

    def _xpath_extract(self, tree: HTMLParser, xpath: str) -> str | None:
        """Return text content of first XPath match (via lxml)."""
        try:
            from lxml import etree

            parser = tree
            # selectolax doesn't support XPath directly, so we use lxml
            root = etree.HTML((parser.html or "").encode())
            els = root.xpath(xpath)
            if not els:
                return None
            text = els[0].text_content().strip()
            return text if text else None
        except Exception:
            return None

    def _apply_field(self, result: StrategyResult, field: str, value: str) -> None:
        """Map a named field to the result object."""
        mapping = {
            "name": "name",
            "phone": "phone",
            "website": "website",
            "address": "address",
            "rating": "rating",
            "reviews": "review_count",
            "link": "extras_link",
        }
        attr = mapping.get(field, field)
        if attr in ("name", "phone", "website", "address"):
            setattr(result, attr, value)
        elif attr == "rating":
            import re

            nums = re.findall(r"[\f\t\n\r]*(\b[0-9.]+)", value)
            if nums:
                result.rating = float(nums[0])
        elif attr == "review_count":
            import re

            nums = re.findall(r"\b([0-9,]+)\b", value.replace(",", ""))
            if nums:
                result.review_count = int(nums[0])
        else:
            result.extras[attr] = value
