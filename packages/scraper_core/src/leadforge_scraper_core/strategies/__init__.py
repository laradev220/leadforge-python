"""Extraction strategy package.

Each strategy implements the ExtractionStrategy protocol defined in base.py.
Strategies are composed by higher-level scrapers in order of reliability:
  1. StructuredDataStrategy  (JSON-LD, microdata, Open Graph)
  2. SelectorStrategy        (per-site YAML/JSON selector config)
  3. RegexStrategy           (emails, phones, social handles)
  4. AIFallbackStrategy      (last resort — ≤5% of pages)
"""

from __future__ import annotations

from leadforge_scraper_core.strategies.base import (
    ExtractionStrategy,
    StrategyResult,
    create_pipeline,
)
from leadforge_scraper_core.strategies.structured import StructuredDataStrategy
from leadforge_scraper_core.strategies.selector import SelectorStrategy
from leadforge_scraper_core.strategies.regex import RegexStrategy
from leadforge_scraper_core.strategies.ai_fallback import AIFallbackStrategy

__all__ = [
    "ExtractionStrategy",
    "StrategyResult",
    "create_pipeline",
    "StructuredDataStrategy",
    "SelectorStrategy",
    "RegexStrategy",
    "AIFallbackStrategy",
]