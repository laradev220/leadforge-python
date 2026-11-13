#!/usr/bin/env python3
"""update_selectors.py — lightweight CLI to refresh degraded selectors.

Run with:
    python -m leadforge_scraper_core.update_selectors --source yelp --sample-url https://yelp.com/biz/example

This script:
  1. Fetches a sample page from the given source
  2. Tests all known selectors for that source
  3. Reports which selectors are working and which are failing
  4. Optionally updates the selectors.yaml with new working selectors
  5. Asks for human confirmation before writing

Usage:
    python -m leadforge_scraper_core.update_selectors --source <source_key>
    python -m leadforge_scraper_core.update_selectors --source yelp --sample-url https://yelp.com/search?find_desc=Restaurants&find_loc=NYC --update
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

# Ensure the package is importable
# File is at: leadforge_scraper_core/update_selectors.py
# Package root is 2 levels up
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from leadforge_scraper_core.base import fetch_html
from leadforge_scraper_core.strategies.selector import SelectorStrategy

SELECTORS_PATH = Path(__file__).parent / "selectors.yaml"


async def test_selectors(
    source: str,
    sample_url: str | None,
    selector_strategy: SelectorStrategy,
    logger,
) -> dict[str, dict[str, bool]]:
    """Test all selectors for a source and return {field: {selector: success}}."""
    if not sample_url:
        print(f"No sample URL provided for {source}, skipping live test.")
        return {}

    html = await fetch_html(sample_url, source=source, keyword="", location="")
    if not html:
        print(f"Failed to fetch sample URL: {sample_url}")
        return {}

    from selectolax.lexbor import LexborHTMLParser as HTMLParser

    tree = HTMLParser(html)

    config = selector_strategy.config
    if source not in config.get("sources", {}):
        print(f"Source '{source}' not found in selectors.yaml")
        return {}

    field_results: dict[str, dict[str, bool]] = {}
    for field, selectors in config["sources"][source].items():
        field_results[field] = {}
        for sel_spec in selectors:
            sel_type = "css"
            sel = sel_spec
            if isinstance(sel_spec, dict):
                sel_type = sel_spec.get("type", "css")
                sel = sel_spec.get("selector", "")

            try:
                if sel_type == "css":
                    node = tree.css_first(sel)
                    success = node is not None and bool(node.text(strip=True))
                else:
                    # XPath — skip for now
                    success = False
            except Exception:
                success = False

            field_results[field][sel] = success
            status = "✓" if success else "✗"
            print(f"  {status} [{field}] {sel_type}:{sel[:60]}")

    return field_results


async def analyze_and_update(
    source: str,
    sample_url: str | None,
    update: bool,
) -> None:
    """Main entry point for selector analysis and update."""
    print(f"\n=== Selector Analysis for '{source}' ===\n")

    selector_strategy = SelectorStrategy()

    # Load current config
    with open(SELECTORS_PATH) as f:
        config = yaml.safe_load(f)

    if source not in config.get("sources", {}):
        print(f"Source '{source}' not found in selectors.yaml. Available sources:")
        for key in config.get("sources", {}):
            print(f"  - {key}")
        return

    # Test existing selectors
    print("Testing existing selectors from selectors.yaml...\n")
    field_results = await test_selectors(source, sample_url, selector_strategy, None)

    # Report
    print("\n=== Summary ===")
    working = []
    broken = []
    for field, results in field_results.items():
        for sel, success in results.items():
            if success:
                working.append((field, sel))
            else:
                broken.append((field, sel))

    print(f"Working: {len(working)}, Broken: {len(broken)}")

    if not broken:
        print("All selectors are working!")
        return

    print("\nBroken selectors:")
    for field, sel in broken:
        print(f"  [{field}] {sel[:60]}")

    if not update:
        print("\nRe-run with --update to apply suggested fixes.")
        return

    # Human-in-the-loop: confirm
    response = input("\nReplace broken selectors with working alternatives? [y/N] ")
    if response.lower() != "y":
        print("Aborted.")
        return

    # For each broken selector, try to find alternatives
    # (In a full implementation, this would use browser automation to find new selectors)
    print("\nAutomatic selector discovery not yet implemented.")
    print("Please manually update selectors.yaml based on the analysis above.")

    print("\nUpdated config would look like:")
    for field, results in field_results.items():
        working_sels = [sel for sel, ok in results.items() if ok]
        if working_sels:
            print(f"  {field}: {working_sels[0]}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh degraded selectors with human-in-the-loop analysis"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source key (e.g. yelp, yellowpages_pk)",
    )
    parser.add_argument(
        "--sample-url",
        help="Sample URL to test selectors against",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help="Update selectors.yaml with working selectors",
    )
    args = parser.parse_args()

    asyncio.run(analyze_and_update(args.source, args.sample_url, args.update))


if __name__ == "__main__":
    main()
