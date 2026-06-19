# CRAWL4AI_ALTERNATIVE.md

# Crawl4AI — Alternative Scraping Engine

Version: 1.0

Status: Draft (Evaluation)

---

# Purpose

Document Crawl4AI as an alternative to Playwright for LeadForge's scraping
layer.

Crawl4AI is an open-source, LLM-first web scraping framework built on top of
Playwright. It provides a higher-level API with built-in Markdown extraction,
structured JSON output, and anti-detection features out of the box.

---

# When to Use Crawl4AI

Use Crawl4AI when:

- LLM-ready data (Markdown, structured JSON) is the primary output
- Anti-detection must work without manual stealth configuration
- Content extraction from business websites needs CSS/LLM-based parsing
- Reducing boilerplate (session management, retries, caching) matters more
  than raw browser control

Use Playwright (current default) when:

- Complex user workflows are required (multi-step interactions, form filling)
- Google Maps requires fine-grained human-motion simulation
- You need full control over every browser API call

---

# Comparison: Crawl4AI vs. Playwright

| Feature | Playwright (Current) | Crawl4AI |
|---|---|---|
| **Primary Use** | Browser automation & testing | AI data extraction |
| **Data Output** | Raw HTML / DOM | Clean Markdown, JSON, LLM-ready |
| **Stealth / Anti-Detection** | Manual (stealth context, fingerprint patches) | Built-in (stealth mode, auto user-agent rotation) |
| **Structured Extraction** | Manual parsing (BeautifulSoup, regex, etc.) | CSS extraction strategies, LLM extraction, cosine similarity |
| **Caching** | Manual | Built-in (session-based cache) |
| **Multi-page Crawling** | Manual | Built-in (auto-link discovery, depth control) |
| **Complexity** | High (full browser control) | Low (designed for data pipelines) |
| **Google Maps Suitability** | ✅ Preferred (human motion control) | ⚠️ Partial (no Maps-specific interaction) |
| **Business Website Extraction** | ✅ Good | ✅ Better (Markdown + structured extraction) |
| **LLM Integration** | ❌ None | ✅ Native (pass schema, get JSON) |

---

# Installation

```bash
pip install crawl4ai
crawl4ai-setup               # Downloads Playwright chromium binaries
```

Optional extras:

```bash
pip install crawl4ai[torch]         # Cosine similarity / clustering
pip install crawl4ai[transformer]   # Local LLM summarization
pip install crawl4ai[all]           # Everything
```

Diagnostics:

```bash
crawl4ai-doctor   # Verify environment, Python version, Playwright
```

---

# Core API

Crawl4AI has four primary components:

---

## AsyncWebCrawler

Entry point. Manages browser instances and crawl lifecycle.

```python
from crawl4ai import AsyncWebCrawler

async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url="https://example.com")
    print(result.markdown[:500])
```

---

## BrowserConfig

Defines **how** the browser behaves.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `headless` | bool | True | Run without UI |
| `proxy` | str | None | Proxy URL (http://user:pass@host:port) |
| `user_agent` | str | auto | Custom user agent |
| `viewport` | dict | 1080p | Viewport dimensions |
| `verbose` | bool | False | Enable verbose logging |
| `ignore_https_errors` | bool | False | Skip SSL errors |

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig

config = BrowserConfig(
    headless=True,
    proxy="http://user:pass@residential.proxy.com:10000",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    viewport={"width": 1920, "height": 1080},
)

async with AsyncWebCrawler(config=config) as crawler:
    result = await crawler.arun(url="https://example.com")
```

---

## CrawlerRunConfig

Defines **what** happens during a specific crawl.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `css_selector` | str | None | Extract only matching elements |
| `extraction_strategy` | BaseExtractionStrategy | None | Strategy for structured data |
| `word_count_threshold` | int | 10 | Minimum word count for content blocks |
| `excluded_tags` | list | None | HTML tags to strip (nav, footer, etc.) |
| `only_text` | bool | False | Return raw text only, no HTML |
| `cache_mode` | CacheMode | ENABLED | Cache control (BYPASS, ENABLED, DISABLED) |
| `wait_for` | str | None | CSS selector to wait for before extraction |

```python
from crawl4ai import CrawlerRunConfig

run_config = CrawlerRunConfig(
    css_selector="main.content",
    word_count_threshold=20,
    excluded_tags=["nav", "footer", "script", "style"],
    only_text=True,
    cache_mode="BYPASS",
)
```

---

## CrawlResult

The output container.

| Field | Type | Description |
|---|---|---|
| `markdown` | str | Clean Markdown version of the page |
| `html` | str | Raw HTML |
| `extracted_content` | str | Result from extraction strategy |
| `links` | list[dict] | Discovered links (href, text) |
| `media` | list[dict] | Images, videos found on page |
| `metadata` | dict | Page metadata (title, description, OG tags) |
| `success` | bool | Whether the crawl succeeded |
| `error_message` | str | Error details if success=False |

```python
result = await crawler.arun(url="https://example.com")

print(result.markdown)          # LLM-ready Markdown
print(result.links[:5])         # First 5 links
print(result.metadata["title"]) # Page title
```

---

# Structured Data Extraction

Crawl4AI supports multiple extraction strategies.

---

## CSS-based Extraction (JsonCssExtractionStrategy)

Best for pages with predictable HTML structure.

```python
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

schema = {
    "name": "Business Name",
    "fields": [
        {"name": "title", "selector": "h1", "type": "text"},
        {"name": "phone", "selector": ".phone", "type": "text"},
        {"name": "email", "selector": "a[href^='mailto:']", "type": "text"},
    ],
}

strategy = JsonCssExtractionStrategy(schema, verbose=True)
run_config = CrawlerRunConfig(
    extraction_strategy=strategy,
    cache_mode="BYPASS",
)
result = await crawler.arun(
    url="https://example.com/contact",
    config=run_config,
)
print(result.extracted_content)  # JSON string
```

---

## LLM-based Extraction (LLMExtractionStrategy)

Best for pages with unstructured content. Pass a schema and an LLM provider.

```python
from crawl4ai.extraction_strategy import LLMExtractionStrategy

strategy = LLMExtractionStrategy(
    provider="openai/gpt-4o",
    api_token="sk-...",
    schema={
        "type": "object",
        "properties": {
            "business_name": {"type": "string"},
            "phone": {"type": "string"},
            "email": {"type": "string"},
            "services": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["business_name"],
    },
    extraction_type="schema",
    instruction="Extract business contact information from this page.",
)

run_config = CrawlerRunConfig(
    extraction_strategy=strategy,
    cache_mode="BYPASS",
)
result = await crawler.arun(
    url="https://example.com",
    config=run_config,
)
print(result.extracted_content)  # Structured JSON
```

---

## Cosine / Clustering Extraction

Uses semantic similarity to identify meaningful content vs. boilerplate.

Requires: `pip install crawl4ai[torch]`

```python
from crawl4ai.extraction_strategy import CosineSimilarityStrategy

strategy = CosineSimilarityStrategy(
    word_count_threshold=15,
    max_dist=0.3,
    top_k=5,
)

run_config = CrawlerRunConfig(
    extraction_strategy=strategy,
    cache_mode="BYPASS",
)
result = await crawler.arun(
    url="https://example.com/about",
    config=run_config,
)
```

---

# Browser Backends

Crawl4AI supports two browser backends.

---

## Playwright (Default)

Full browser engine. Required for JavaScript-heavy sites.

```python
config = BrowserConfig(browser_type="chromium")
```

Pros:

- Executes JavaScript
- Handles dynamic content (React, Vue, Angular)
- Supports stealth mode

Cons:

- Slower (full browser overhead)
- More resource-intensive

---

## HTTP Backend

Direct HTTP requests for static HTML pages. Much faster.

```python
from crawl4ai import AsyncWebCrawler, BrowserConfig

config = BrowserConfig(
    browser_type="chromium",
    use_http_backend=True,  # Skip browser, use HTTP directly
)
```

Pros:

- Very fast (no browser overhead)
- Low resource usage
- Good for simple pages

Cons:

- No JavaScript execution
- Won't render dynamic content

---

# Anti-Detection Features

---

## Stealth Mode

Enables automatic anti-detection patches.

- `navigator.webdriver` set to `false`
- Realistic `navigator.plugins` array
- WebGL vendor/renderer randomization
- Canvas fingerprint noise
- User-Agent rotation per session

```python
config = BrowserConfig(
    headless=True,
    stealth=True,       # Enable anti-detection
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
)
```

---

## Proxy Support

Pass any proxy type (datacenter, residential, rotating).

```python
config = BrowserConfig(
    proxy="http://user:pass@residential.proxy.com:10000",
)
```

---

## User-Agent Management

Automatic UA rotation when not explicitly set.

---

# Caching System

Crawl4AI caches results by default to avoid re-crawling the same URL.

```python
from crawl4ai import CacheMode

# Bypass cache for fresh data
run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)

# Enable cache (default)
run_config = CrawlerRunConfig(cache_mode=CacheMode.ENABLED)

# Disable cache entirely
run_config = CrawlerRunConfig(cache_mode=CacheMode.DISABLED)
```

---

# LeadForge Integration Strategy

Crawl4AI can be added as a **secondary scraping engine** alongside Playwright.

---

## Architecture

```text
scraper_core/
  base.py                # Existing — fetch_html (httpx + Playwright)
  crawl4ai_bridge.py     # NEW — Crawl4AI wrapper
  google_maps.py         # Existing — Playwright only (human motion)
  website.py             # Existing — can use Crawl4AI as backend
  contact.py             # Existing — can use Crawl4AI as backend
```

Rule:

- Google Maps → Playwright only (Crawl4AI doesn't have Maps-specific
  interaction helpers)
- Business websites → Crawl4AI preferred (better Markdown extraction,
  built-in caching, structured output)
- Contact extraction → Crawl4AI preferred (CSS extraction strategy)

---

## Integration: Crawl4AI Bridge

```python
"""crawl4ai_bridge.py — Wrapper for Crawl4AI in LeadForge."""

from __future__ import annotations

from typing import Any

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.extraction_strategy import JsonCssExtractionStrategy

from leadforge_config import get_settings


async def crawl_markdown(url: str) -> str | None:
    """Fetch a page and return clean Markdown."""
    settings = get_settings()
    config = _build_browser_config(settings)
    run_cfg = CrawlerRunConfig(
        word_count_threshold=10,
        excluded_tags=["nav", "footer", "script", "style"],
        cache_mode="BYPASS",
    )

    try:
        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun(url, config=run_cfg)
            if result.success:
                return result.markdown
    except Exception:
        pass
    return None


async def extract_business_contacts(url: str) -> dict[str, Any] | None:
    """Extract structured contact info from a business website."""
    schema = {
        "name": "Business Contact",
        "fields": [
            {"name": "email", "selector": "a[href^='mailto:']", "type": "text"},
            {"name": "phone", "selector": "[class*='phone'], [class*='tel']", "type": "text"},
            {"name": "address", "selector": "[class*='address']", "type": "text"},
        ],
    }
    strategy = JsonCssExtractionStrategy(schema, verbose=False)
    config = _build_browser_config(get_settings())
    run_cfg = CrawlerRunConfig(
        extraction_strategy=strategy,
        cache_mode="BYPASS",
    )

    try:
        async with AsyncWebCrawler(config=config) as crawler:
            result = await crawler.arun(url, config=run_cfg)
            if result.success and result.extracted_content:
                import json  # noqa: PLC0415 — local import avoids top-level dependency
                return json.loads(result.extracted_content)
    except Exception:
        pass
    return None


def _build_browser_config(settings: Any) -> BrowserConfig:
    """Build Crawl4AI BrowserConfig from LeadForge settings."""
    return BrowserConfig(
        headless=settings.playwright_headless,
        proxy=settings.playwright_proxy_url or None,
        verbose=False,
    )
```

---

## Integration: Replacing fetch_html for Website Crawling

The existing `fetch_html()` in `base.py` can fall back to Crawl4AI when
Playwright fails or when Markdown output is needed.

After adding `crawl4ai_bridge.py`, update `scraper_core/__init__.py` to
re-export the new functions (matching the existing pattern where
`search_businesses`, `analyze_website`, etc. are exported).

```python
# In base.py — optional fallback

async def fetch_html_with_fallback(url: str) -> str | None:
    """Try Playwright first, then Crawl4AI for clean Markdown."""

    # 1. Try existing Playwright path
    html = await fetch_html(url, use_playwright=True)
    if html:
        return html

    # 2. Fall back to Crawl4AI
    try:
        from leadforge_scraper_core.crawl4ai_bridge import crawl_markdown
        return await crawl_markdown(url)
    except ImportError:
        return None
```

---

# Migration Path

Step 1 — Evaluation

```text
pip install crawl4ai
```

Test `crawl_markdown()` on 10 business websites.

Compare output quality vs. current Playwright extraction.

---

Step 2 — Parallel Operation

```text
Website Worker
  ├── Playwright path (current)
  └── Crawl4AI path (new, env-gated)
```

Toggle via env:

```text
SCRAPER_ENGINE=playwright   # default
SCRAPER_ENGINE=crawl4ai     # experimental
```

---

Step 3 — Full Adoption

If Crawl4AI proves superior:

```text
- Replace Playwright in website/contact/social workers
- Keep Playwright only for Google Maps
- Remove manual stealth-context code
- Remove manual Markdown conversion
```

---

# Known Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| Google Maps interaction | Not supported | Keep Playwright for Maps |
| No human-motion simulation | Higher ban risk on strict sites | Use Playwright fallback |
| LLM strategy costs $ | GPT-4o calls add up | Use CSS strategy for structured pages |
| torch dependency | Heavy (1-2 GB) | Optional, skip if not using cosine |

---

# Codex Rules

1. Crawl4AI is a supplement, not a replacement for Playwright.
2. Google Maps must always use Playwright (human motion required).
3. All Crawl4AI code must live in `scraper_core/crawl4ai_bridge.py`.
4. Toggle between engines via env variable, never hardcoded.
5. Never use LLM extraction for high-volume scraping — only for enrichment.
6. Cache results aggressively to avoid re-crawling the same URL.
7. Proxy configuration must pass through LeadForge's existing env vars.
8. Keep the Crawl4AI bridge thin — no business logic, only scraping logic.
