"""StructuredDataStrategy — extracts from JSON-LD, microdata, and Open Graph.

This is the most reliable strategy because these formats are standardised and
rarely change.  It should run first (priority=0).
"""

from __future__ import annotations

import json
import re
from typing import Any

from selectolax.parser import HTMLParser

from leadforge_scraper_core.strategies.base import (
    ExtractionStrategy,
    StrategyResult,
)


class StructuredDataStrategy(ExtractionStrategy):
    """Extract structured metadata from JSON-LD, microdata, and Open Graph."""

    name = "structured"
    priority = 0

    # Regex to find JSON-LD script tags
    _JSONLD_RE = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE,
    )

    def can_handle(self, html: str) -> bool:
        return bool(
            '<script type="application/ld+json"' in html
            or '<meta property="og:' in html
            or "itemscope" in html
            or "itemtype" in html
        )

    async def extract(
        self,
        html: str,
        url: str,
        *,
        logger: Any = None,
    ) -> StrategyResult | None:
        tree = HTMLParser(html)
        result = StrategyResult(strategy_name=self.name)

        # 1. JSON-LD
        jsonld_data = self._extract_jsonld(html)
        if jsonld_data:
            self._apply_jsonld(jsonld_data, result)

        # 2. Open Graph
        og_data = self._extract_og(tree)
        if og_data:
            self._apply_og(og_data, result)

        # 3. Microdata
        microdata = self._extract_microdata(tree)
        if microdata:
            self._apply_microdata(microdata, result)

        # Only return result if we found something meaningful
        if result.name or result.phone or result.email or result.address:
            result.confidence = 95
            return result
        return None

    # ── JSON-LD helpers ──────────────────────────────────────────────────────

    def _extract_jsonld(self, html: str) -> list[dict[str, Any]]:
        """Find and parse all JSON-LD blocks in the HTML."""
        results = []
        for match in self._JSONLD_RE.finditer(html):
            try:
                data = json.loads(match.group(1))
                # JSON-LD can wrap a list or a single dict
                if isinstance(data, list):
                    results.extend(data)
                elif isinstance(data, dict):
                    results.append(data)
            except (json.JSONDecodeError, ValueError):
                pass
        return results

    def _apply_jsonld(self, data: list[dict[str, Any]], result: StrategyResult) -> None:
        """Extract into result from a list of JSON-LD graphs."""
        for item in data:
            self._extract_local_business(item, result)
            # Handle @graph structure
            if "@graph" in item and isinstance(item["@graph"], list):
                for node in item["@graph"]:
                    self._extract_local_business(node, result)

    def _extract_local_business(self, item: dict[str, Any], result: StrategyResult) -> None:
        """Extract LocalBusiness or related types from a JSON-LD node."""
        typ = item.get("@type", "")
        # Allow single string or list
        if isinstance(typ, list):
            typ = typ[0] if typ else ""
        typ = str(typ)

        if "LocalBusiness" in typ or "Restaurant" in typ or "ProfessionalService" in typ:
            result.name = result.name or item.get("name")
            result.address = self._extract_address(item.get("address"))
            result.phone = result.phone or item.get("telephone")
            result.website = result.website or item.get("url")
            if "geo" in item:
                result.latitude = item["geo"].get("latitude")
                result.longitude = item["geo"].get("longitude")
            if "aggregateRating" in item:
                result.rating = self._safe_float(item["aggregateRating"].get("ratingValue"))
                result.review_count = self._safe_int(item["aggregateRating"].get("reviewCount"))
            result.extras["jsonld_type"] = typ

    def _extract_address(self, addr: Any) -> str | None:
        """Normalise a JSON-LD address dict or string to a single string."""
        if addr is None:
            return None
        if isinstance(addr, str):
            return addr
        if isinstance(addr, dict):
            parts = [
                addr.get("streetAddress"),
                addr.get("addressLocality"),
                addr.get("addressRegion"),
                addr.get("postalCode"),
                addr.get("addressCountry"),
            ]
            # Filter out None/empty parts to avoid double commas
            return ", ".join(p.strip() for p in parts if p and str(p).strip())
        return None

    # ── Open Graph helpers ───────────────────────────────────────────────────

    def _extract_og(self, tree: HTMLParser) -> dict[str, str]:
        """Extract all og:meta properties."""
        data = {}
        for meta in tree.css('meta[property^="og:"]'):
            prop = (meta.attrs.get("property") or "")[3:]  # strip "og:"
            content = meta.attrs.get("content") or ""
            if prop and content:
                data[prop] = content
        return data

    def _apply_og(self, og: dict[str, str], result: StrategyResult) -> None:
        result.name = result.name or og.get("title")
        result.website = result.website or og.get("url")
        result.extras["og_description"] = og.get("description")

    # ── Microdata helpers ────────────────────────────────────────────────────

    def _extract_microdata(self, tree: HTMLParser) -> dict[str, Any]:
        """Find all itemtype=Schema.org nodes and extract their properties."""
        data = {}
        for item in tree.css("[itemscope][itemtype]"):
            typename = (item.attrs.get("itemtype") or "").split("/")[-1]
            props = {}
            for prop_el in item.css("[itemprop]"):
                prop_name = prop_el.attrs.get("itemprop") or ""
                tag = prop_el.tag
                if tag == "meta":
                    val = prop_el.attrs.get("content", "")
                elif tag in ("a", "link"):
                    val = prop_el.attrs.get("href", "")
                else:
                    val = prop_el.text(strip=True)
                if prop_name:
                    props[prop_name] = val
            if typename:
                data[typename] = props
        return data

    def _apply_microdata(self, microdata: dict[str, Any], result: StrategyResult) -> None:
        for _typename, props in microdata.items():
            if "name" in props and not result.name:
                result.name = props["name"]
            if "telephone" in props and not result.phone:
                result.phone = props["telephone"]
            if "url" in props and not result.website:
                result.website = props["url"]
            if "address" in props and not result.address:
                if isinstance(props["address"], dict):
                    result.address = self._extract_address(props["address"])
                else:
                    result.address = props["address"]

    # ── Utilities ────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_float(val: Any) -> float | None:
        try:
            return float(val)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(val: Any) -> int | None:
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
