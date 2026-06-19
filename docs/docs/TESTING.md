# TESTING.md

# LeadForge AI – Testing Strategy

Version: 2.0

Status: Mandatory

---

# PURPOSE

This document defines testing strategy for all components:

* API
* Workers
* Scrapers
* Scoring engine
* Queue system

---

# TESTING PHILOSOPHY

LeadForge is a:

> deterministic pipeline system

Therefore:

* same input MUST always produce same output
* no flaky logic allowed
* no hidden randomness

---

# TEST LEVELS

## 1. UNIT TESTS

Scope:

* functions
* utilities
* scoring engine
* parsers

Tools:

* pytest + pytest-asyncio
* fakeredis (Redis mock for tests)
* freezegun (time mocking for scoring)

---

### Required Unit Tests

* lead scoring calculation
* email extraction
* phone normalization
* duplicate detection logic
* extraction strategies (structured data, regex, selector)
* monitors (circuit breaker, rate limiter)
* cache operations

---

## 2. INTEGRATION TESTS

Scope:

* worker + queue + database flow

Example:

```text
Search Job → Discovery Worker → DB Insert
```

Must verify:

* job creation
* queue processing
* database persistence

Tools:

* pytest + pytest-asyncio
* real PostgreSQL (via Docker) or testcontainers
* real Redis (via Docker) or fakeredis

---

## 3. WORKER TESTS

Each worker MUST be tested independently.

Test Flow:

```text
Mock Job → Worker → Validate DB Output
```

Workers tested:

* discovery-worker
* website-worker
* contact-worker
* social-worker
* scoring-worker

---

## 4. API TESTS

Scope:

* endpoints
* authentication
* validation
* response format

Tools:

* pytest
* httpx (AsyncClient for FastAPI TestClient)

Rules:

* no business logic tested here
* only request/response behavior

---

## 5. END-TO-END TESTS (MINIMAL)

Scope:

* full pipeline flow

Example:

```text
Search Job → Lead Output → Export CSV
```

Must confirm:

* system is fully functional

---

# TEST DATA RULES

* use fake business data
* never hit real websites in tests
* mock external scraping
* use static HTML fixtures for scraper tests (see `tests/unit/fixtures/`)

---

# SCRAPER TESTING RULES

Scrapers MUST:

* be tested with static HTML fixtures
* not rely on live websites
* support deterministic outputs
* mock Playwright/httpx external calls

---

# SCORING TEST RULES

Lead scoring MUST be:

* deterministic
* reproducible

Test must verify:

```text
Same input → Same score always
```

---

# MOCKING RULES

Allowed mocks:

* HTTP responses (via httpx mocking or respx)
* HTML pages (static fixtures)
* API calls
* Redis (via fakeredis)

Forbidden:

* random data generation in core logic tests
* live scraping in CI

---

# PERFORMANCE TESTING

Required metrics:

* 10k businesses processing simulation
* queue throughput stability
* worker concurrency limits

---

# FAILURE TESTING

Must test:

* worker crash recovery
* queue retry behavior
* malformed HTML handling
* invalid business data handling

---

# CI REQUIREMENTS

Pipeline must:

* run unit tests (`uv run pytest tests/unit/ -v`)
* run integration tests (`uv run pytest tests/integration/ -v`)
* run linter (`uv run ruff check`)
* run type checker (`uv run mypy`)
* block merge on failure

---

# CODE COVERAGE TARGET

Minimum:

```text
80% core logic coverage
```

Focus areas:

* scoring engine
* extraction logic
* deduplication logic

---

# TESTING PRINCIPLES

1. Deterministic behavior only
2. No flaky tests
3. No dependency on external systems for unit tests
4. Workers must be independently testable
5. API must remain thin and test-free of logic
6. Pipeline must be reproducible

---

# TOOLS SUMMARY

| Tool | Purpose |
|---|---|
| pytest | Test runner |
| pytest-asyncio | Async test support |
| pytest-cov | Coverage reporting |
| ruff check | Linting |
| mypy | Static type checking |
| fakeredis | Redis mock for tests |
| freezegun | Time mocking for scoring tests |
| httpx | HTTP client + FastAPI TestClient |
| respx | HTTP request mocking |

---

# FINAL RULE

If a feature cannot be tested:

> It should not be shipped
