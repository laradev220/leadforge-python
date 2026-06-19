# SCRAPING_STRATEGY.md

# LeadForge AI Scraping & Enrichment Strategy

Version: 1.0

Status: Approved

---

# Purpose

The purpose of the scraping engine is not simply to collect business listings.

The purpose is:

1. Discover businesses
2. Discover websites
3. Discover contact methods
4. Discover social profiles
5. Calculate contact confidence
6. Determine the best outreach channel

The final output should answer:

```json
{
  "business": "",
  "bestContactMethod": "",
  "leadScore": 0
}
```

---

# Core Principle

Discovery never stops at the first result.

Example:

```text
Google Maps
   ↓
Phone Found
```

Most scrapers stop here.

LeadForge continues:

```text
Google Maps
    ↓
Website Discovery
    ↓
Website Crawl
    ↓
Email Discovery
    ↓
Contact Discovery
    ↓
Social Discovery
    ↓
Lead Scoring
```

---

# Discovery Pipeline

```text
Search Job
     ↓
Business Discovery
     ↓
Website Discovery
     ↓
Website Validation
     ↓
Contact Extraction
     ↓
Social Discovery
     ↓
Social Enrichment
     ↓
Lead Scoring
```

Every stage is independent.

Every stage can be retried.

Every stage can scale independently.

---

# Business Discovery Strategy

Goal:

Create a business record.

Collect:

```text
Business Name
Category
Address
Phone
Rating
Review Count
Website (if available)
Coordinates
```

---

# Business Normalization

Before storage:

Normalize:

```text
Name
Phone
Website
Address
```

Example:

```text
ABC Dental LLC
ABC Dental
```

Should be treated as similar candidates.

---

# Deduplication Strategy

A business is considered duplicate if:

Priority 1:

```text
Same External ID
```

Priority 2:

```text
Same Name
Same Address
```

Priority 3:

```text
Same Phone
```

Priority 4:

```text
Same Website Domain
```

Duplicates should update existing records.

Never create new records.

---

# Website Discovery Strategy

Goal:

Find the official website.

---

## Case 1

Website already available.

Example:

```text
Website Found
```

Action:

```text
Validate
```

---

## Case 2

Website Missing

Action:

Create Website Discovery Job.

Search Candidates:

```text
Business Name
Business Name + City
Business Name Official Website
Business Name Contact
```

---

# Website Confidence Scoring

Every discovered website receives confidence.

Factors:

```text
Business Name Match
Domain Match
Phone Match
Address Match
```

Example:

```text
Domain Contains Name      +40
Phone Matches             +30
Address Matches           +30
```

Score:

```text
0-100
```

Only websites above threshold should be marked as official.

---

# Website Validation

Required Checks:

```text
DNS Resolves
HTTPS Available
Page Loads
```

Store:

```text
Status Code
Load Time
SSL
```

---

# Website Crawling Strategy

Maximum Depth:

```text
2
```

Maximum Pages:

```text
20
```

Reason:

Most contact information appears in:

```text
Homepage
Contact
About
Team
Footer
```

No need to crawl entire websites.

---

# High Priority Pages

Always prioritize:

```text
/
```

```text
/contact
```

```text
/about
```

```text
/contact-us
```

```text
/about-us
```

```text
/team
```

---

# Contact Discovery Strategy

Goal:

Find all public contact methods.

---

# Email Discovery

Search:

```text
HTML
Text Content
Footer
Contact Pages
Structured Data
```

Email Pattern:

```regex
[a-zA-Z0-9._%+-]+@
[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}
```

---

# Email Confidence

High Confidence:

```text
info@
hello@
contact@
support@
admin@
```

Medium Confidence:

```text
firstname@
lastname@
```

Low Confidence:

```text
third-party domains
```

Example:

```text
gmail.com
hotmail.com
```

---

# Phone Discovery

Extract:

```text
tel:
visible numbers
contact pages
```

Normalize:

```text
E.164
```

Example:

```text
+923001234567
```

---

# Phone Confidence

High:

```text
Phone appears on:
Maps
Website
Social Profile
```

Medium:

```text
Website only
```

Low:

```text
Single appearance
```

---

# Contact Form Discovery

Detect:

```html
<form>
```

with fields:

```text
name
email
message
phone
```

Store:

```text
Contact Form URL
```

Do not submit forms automatically.

---

# Social Discovery Strategy

Goal:

Find official business profiles.

---

# Supported Platforms

```text
Facebook
Instagram
LinkedIn
YouTube
TikTok
X
```

---

# Social Sources

Discover from:

Website Footer

Example:

```html
facebook.com/company
instagram.com/company
```

Structured Metadata

OpenGraph

Public Links

Business Profiles

---

# Social Confidence Score

High:

```text
Linked from Website
```

Score:

```text
100
```

Medium:

```text
Business Name Match
```

Score:

```text
70
```

Low:

```text
Weak Match
```

Score:

```text
40
```

---

# Social Enrichment

Collect if publicly visible:

```text
Username
Followers
Following
Bio
Website
Public Email
Public Phone
```

---

# Social Activity Detection

Determine:

```text
Last Activity Date
```

Classification:

```text
ACTIVE
MODERATE
INACTIVE
```

---

# Website Opportunity Detection

This is the core LeadForge feature.

---

# Opportunity Type A

No Website

Score:

```text
Very High
```

Reason:

Immediate website prospect.

---

# Opportunity Type B

Website Exists

But:

```text
No SSL
Slow
Outdated
No Contact Form
```

Score:

```text
High
```

---

# Opportunity Type C

Modern Website

Score:

```text
Low
```

---

# Best Contact Method Strategy

Priority:

```text
EMAIL
CONTACT_FORM
WHATSAPP
LINKEDIN
FACEBOOK
INSTAGRAM
PHONE
```

System must determine:

```json
{
  "bestContactMethod": ""
}
```

for every business.

---

# Enrichment Completion Rules

Business is considered enriched when:

At least one:

```text
Email
Phone
Contact Form
Social Profile
```

exists.

OR

All enrichment strategies have completed.

---

# Retry Strategy

Worker Failures:

```text
3 Attempts
```

Backoff:

```text
Exponential
```

Never retry infinitely.

---

# Rate Limiting

Required.

Workers must support:

```text
Concurrency Limits
Request Delays
Throttling
```

Configuration through:

```text
ENV Variables
```

---

# Data Quality Rules

Reject:

```text
Empty Names
Broken URLs
Malformed Emails
Invalid Phones
```

Normalize before storage.

---

# Observability

Every enrichment step must log:

```json
{
  "businessId": "",
  "worker": "",
  "status": "",
  "duration": ""
}
```

---

# Codex Rules

1. Discovery and enrichment are separate concerns.
2. Never mix worker responsibilities.
3. Normalize data before persistence.
4. Score confidence for discovered assets.
5. Never assume website ownership.
6. Validate all contact information.
7. Use deterministic enrichment pipelines.
8. Log every enrichment action.
9. Prefer quality over quantity.
10. Lead quality is more important than scraping volume.

---

# Google Maps Extraction Approach

The Google Maps scraper (`packages/scraper_core/src/leadforge_scraper_core/google_maps.py`)
has been reworked to use **side panel extraction** rather than opening individual place pages.

## Why Side Panel?

Google Maps place pages load business data (phone, website, rating) via **protobuf RPC**
(`batchexecute` endpoint) that is not accessible from HTML or DOM inspection.
However, the **search results page** loads this data into the DOM when you click
on a feed item — the side panel on the left side of the page renders phone,
website, review count, and full address via XHR.

## Extraction Flow

```text
Search Results Page Loaded
    │
    ▼
1. Scroll feed with human-like motion (accelerated/decelerated wheel ticks)
    │
    ▼
2. Extract feed metadata from ARIA labels and text:
   • Name from [aria-label] (first non-generic label)
   • Rating from "4.5 stars" pattern in ARIA labels
   • Review count from "4.7 stars 3,901 Reviews" pattern
   • Address/category from feed item text (parsed by · separators)
    │
    ▼
3. For each feed item:
   • Click the item link using Playwright locator (auto-scrolls into view)
   • Wait 3-5s for side panel XHR data to load
   • Extract phone from DOM lines matching /^\+[\d\s\-()]+$/
   • Extract website from DOM lines containing domain (no spaces, non-Google)
   • Extract review_count from lines like "(15,287)"
   • Extract full address from lines matching street, city, postcode pattern
   • Close panel with Escape key
    │
    ▼
4. Build MapsBusiness result (name/category/phone/website/address/rating/review_count)
```

## Benefits

- **Reliable phone extraction** — phone numbers like `+44 20 7287 2200` are present in the DOM
- **Reliable website extraction** — domains like `pizzapilgrims.co.uk` appear as single-token lines
- **No CSS selectors needed** — no brittle selector maintenance
- **No protobuf parsing** — data is already rendered into DOM by Google's JS
- **~150 lines of dead code removed** — old approach relied on opening new pages and trying to extract from non-rendered data

## Rate Limiting & Human Simulation

- Randomized delays between each action (500-5000ms)
- Variable scroll distances (400-900px per scroll)
- Multiple small wheel ticks (4-8 steps) with jitter
- Randomized viewport and user agent per session
- Circuit breaker with exponential backoff (3 retries, max 30s wait)
- 120-second overall timeout for a single search

---

# 11. Network & Stealth Ops

The scraping layer is hardened against anti-bot detection and IP-based rate
limiting via two cooperating layers.

---

## 11.1 Network Layers

```text
Discovery Worker  ──► Playwright (human simulation, stealth context)  ──► Google Maps
Enrichment Worker ──► Playwright (stealth + resource blocking)          ──► Business websites
Background Jobs   ──► httpx / aiohttp (proxied requests)                 ──► WHOIS, DNS, lookups
```

Playwright owns browser-driven scraping because it can authenticate proxies
and execute JavaScript. Background HTTP tasks use `httpx` or `aiohttp` with
proxy support from config.

---

## 11.2 Stealth Playwright Context

Implemented in `packages/scraper_core/src/leadforge_scraper_core/human_simulation.py`.
Applies fingerprint overrides Google actively checks:

- `navigator.webdriver` double-stamped to `false`.
- `navigator.plugins` set to a realistic plugin array.
- WebGL vendor/renderer pinned to Intel Iris Pro (Google-specific).
- Canvas `toDataURL` seeded with session-specific noise.
- UA pool rotated per context (Chrome 131 Win/Mac/Linux).
- Viewport pool: 1920x1080, 1440x900, 1366x768, 1536x864.
- Resource blocking at the route layer (images, fonts, analytics) to save
  proxy bandwidth on the enrichment path.

---

## 11.3 Proxy Pool

Configured through `leadforge_config.settings.Settings`.

- **Sticky sessions**: same `queryId` → same IP for the duration of a single
  search query. Format: `<user>-session-<ttl>-<rand>` (Bright Data / Smartproxy
  convention).
- **Rotation**: new `queryId` → new IP.
- **Failover chain**: `PROXY_FALLBACK_LIST` parsed from env as
  `protocol|host|port|user|pass;...`.
- **Fail-loud posture**: if `PROXY_PROVIDER` is set, all credentials are
  required or the worker crashes on boot. No silent unscraped exposure.

---

## 11.4 Proxied HTTP Requests

For non-Playwright background jobs (WHOIS, DNS validation on extracted
domains), the `httpx` client is configured with proxy settings from the
shared config:

```python
from leadforge_config import get_settings

settings = get_settings()
proxies = {
    "http://": f"socks5://{settings.proxy_user}:{settings.proxy_pass}@{settings.proxy_host}:{settings.proxy_port}",
    "https://": f"socks5://{settings.proxy_user}:{settings.proxy_pass}@{settings.proxy_host}:{settings.proxy_port}",
}
```

- Config template: `infra/proxychains/proxychains4.conf.template`
- Install: `sudo infra/proxychains/install.sh`

---

## 11.5 Human Motion

Implemented in `packages/scraper_core/src/leadforge_scraper_core/human_simulation.py`
as `human_delay`, `human_scroll`, `human_type`, etc.:

- `human_delay(min_ms, max_ms, page)` — randomized wait with crypto-strength
  randomness, optional tab blur simulation.
- `human_scroll(page, total_distance, steps)` — scrolls in 4–8 small wheel
  ticks with accelerating/decelerating deltas, randomized intervals between
  each tick (100–500ms).
- `human_type(page, selector, text)` — character-by-character typing with
  randomized inter-keystroke delays (50–200ms).

---

## 11.6 Ban Detection & Circuit Breaker

Handled by `packages/scraper_core/src/leadforge_scraper_core/monitors/circuit_breaker.py`:

| Kind | Source | Action |
|---|---|---|
| `403` | Forbidden | Circuit opens, cooldown 15–45s |
| `429` | Rate Limited | Circuit opens, cooldown 15–45s |
| `503` | Unavailable | Circuit opens, cooldown 15–45s |
| `CAPTCHA` | cf-email, g-recaptcha, hcaptcha, "unusual traffic" | Throw `CaptchaDetected` — job marked FAILED, **no auto-retry** |
| `EMPTY` | body < 200 bytes | Retry, circuit monitors consecutive failures |

The circuit breaker uses exponential backoff (3 retries, max 30s wait) and
resets after a successful request. All states (`CLOSED`, `OPEN`, `HALF_OPEN`)
are tracked in memory with per-domain isolation.

Rate limiting is additionally handled by `monitors/rate_limiter.py` with
per-domain request windows, configurable max concurrency, and jitter delays.

CAPTCHA bypass is **forbidden** per SECURITY.md. Detection is terminal.

---

## 11.7 Multi-Page Enrichment

Implemented in the website worker (`workers/website_worker/`):

1. Fetch `/` (homepage) via Playwright for JS-rendered content.
2. Crawl up to 20 pages, max depth 2 (configurable).
3. Prioritize `/contact`, `/about`, `/contact-us`, `/about-us`, `/team`.
4. Abort early once an email and a phone are both present.
5. Resource-block images/CSS/fonts/analytics to save bandwidth.

---

## 11.8 Configuration

All knobs are env-driven, validated by `leadforge_config.settings.Settings`:

```text
PROXY_PROVIDER / PROXY_HOST / PROXY_PORT / PROXY_USER / PROXY_PASS
PROXY_PROTOCOL / PROXY_STICKY_TTL_S / PROXY_FALLBACK_LIST
SCRAPER_TIMEOUT_MS / SCRAPER_JITTER_MIN_MS / SCRAPER_JITTER_MAX_MS
SCRAPER_BAN_COOLDOWN_MIN_MS / SCRAPER_BAN_COOLDOWN_MAX_MS
```

