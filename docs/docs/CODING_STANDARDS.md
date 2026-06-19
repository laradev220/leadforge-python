# LeadForge AI – Coding Standards

Version: 2.0

Status: Mandatory

---

# Purpose

This document defines strict coding conventions for all services, workers, and packages in LeadForge AI.

All generated code MUST follow these rules.

Failure to follow these rules results in inconsistent architecture, unmaintainable workers, and broken enrichment pipelines.

---

# Core Principles

Code in LeadForge AI must be:

* Predictable
* Modular
* Deterministic
* Testable
* Queue-driven
* Stateless where required

---

# LANGUAGE STANDARD

## Backend

* Python 3.12+
* FastAPI
* SQLAlchemy 2.0 (async)
* Pydantic v2

## Workers

* Python 3.12+
* Arq (async queue consumer)
* SQLAlchemy 2.0 (async ORM)

No JavaScript files allowed in production code.

---

# PROJECT STRUCTURE RULES

## API

```text
apps/api/src/leadforge_api/
  routes/          # Thin route handlers (FastAPI routers)
  services/        # Business logic
  schemas/         # Pydantic request/response models
  core/            # Shared utilities (auth, errors, response, queue)
```

Rules:

* Routes → parse input, call service, return response
* Services → all business logic
* Schemas → validation + serialization
* Core → shared infrastructure

## WORKERS

```text
workers/
  discovery_worker/
  website_worker/
  contact_worker/
  social_worker/
  scoring_worker/
  export_worker/
```

Rules:

* One worker = one responsibility
* Workers must not share state
* Workers must be idempotent
* Each worker has a single `main.py` with the processor + `WorkerWrapper`

## SHARED PACKAGES

```text
packages/
  config/        # pydantic-settings (Settings class)
  shared/        # Types, constants, scoring engine, utilities
  database/      # SQLAlchemy models + Alembic migrations
  worker_core/   # Arq WorkerWrapper, queue helpers
  scraper_core/  # Playwright, httpx, extraction strategies
```

Rules:

* `shared/` — no business logic, only reusable types, constants, and utility functions
* `database/` — ORM models only, no business logic
* `worker_core/` — queue infrastructure only
* `scraper_core/` — scraping logic only

---

# NAMING CONVENTIONS

## Files

* snake_case

```text
lead_service.py
business_parser.py
contact_extractor.py
```

## Classes

* PascalCase

```text
BusinessService
LeadScoringEngine
ContactExtractor
```

## Functions & Methods

* snake_case

```text
extract_emails()
calculate_lead_score()
normalize_phone()
```

## Variables

* snake_case only

## Constants

* UPPER_SNAKE_CASE

```text
MAX_RETRIES
DEFAULT_TIMEOUT
SCORING_WEIGHTS
```

## Private Functions

* `_` prefix for module-private (non-exported) functions

```text
_normalize_phone()
_is_placeholder_name()
```

## Type Hints

Always use type hints.

```python
def normalize_phone(phone: str | None) -> str | None:
    ...
```

---

# SERVICE DESIGN RULES

## Services MUST:

* Be stateless
* Be reusable
* Have single responsibility
* Accept dependencies explicitly (FastAPI Depends or direct import)

## Services MUST NOT:

* Call HTTP endpoints directly (except via dedicated client packages)
* Perform scraping (must use workers)
* Contain queue logic
* Contain routing logic

---

# WORKER DESIGN RULES

Each worker MUST:

* Process one queue only
* Be independently runnable
* Be restart-safe
* Be idempotent

## Worker Flow Pattern

```text
Receive Job (Arq)
   ↓
Validate Input
   ↓
Open DB Session (get_session_ctx)
   ↓
Process Task
   ↓
Update Database
   ↓
Enqueue Next Job (enqueue_job)
   ↓
Return
```

---

# API DESIGN RULES

Route handlers MUST:

* Never exceed 30 lines
* Never contain business logic
* Only call services
* Always use Pydantic schemas for request/response

Services MUST:

* Handle all logic
* Be testable independently

---

# ERROR HANDLING RULES

## Standard Error Format

```json
{
  "code": "ERROR_CODE",
  "message": "Human readable message",
  "context": {}
}
```

## Rules

* Never throw raw exceptions to API — always normalize through `AppError`
* Always log full error internally via structlog
* Use HTTPException or custom `AppError` subclasses

---

# LOGGING STANDARDS

Use structured logging only (structlog).

Format:

```json
{
  "event": "job_completed",
  "service": "website-worker",
  "jobId": "",
  "businessId": "",
  "duration": 0
}
```

---

# DATABASE ACCESS RULES

* Only use SQLAlchemy async ORM
* No raw SQL unless absolutely necessary
* Always use upserts for business entities
* Never duplicate records
* Use `expire_on_commit=False` to avoid stale state issues
* Extract ORM fields to local variables before nested async calls to prevent MissingGreenlet errors

---

# ASYNC & QUEUE RULES

* All long-running tasks MUST use Arq
* No blocking operations in API
* No direct scraping in route handlers
* Use `async with get_session_ctx()` for all DB operations

---

# PERFORMANCE RULES

* Avoid N+1 queries (use `selectinload` or `joinedload` for relations)
* Always paginate results (page/limit pattern, max 100 per page)
* Use database indexes for all filter/sort columns
* Prefer batch operations in workers

---

# SECURITY RULES

* Never expose internal worker data to API
* Validate all external inputs via Pydantic
* Sanitize scraped data
* Never trust external HTML content
* JWT required for all protected endpoints

---

# SCRAPING RULES

* Always use Playwright or httpx in workers only
* Respect rate limits (human-like delays, randomized timing)
* Never parallelize uncontrolled scraping
* Always normalize extracted data (phone, website, address)
* Use circuit breakers for all external sources
* Human-like motion simulation for Google Maps

---

# IDENTITY RULES

* UUIDs only (PG_UUID with as_uuid=True)
* Never use incremental IDs
* External IDs must always be preserved

---

# TESTING RULES

## Required Tests

* Lead scoring engine (deterministic, reproducible)
* Contact extraction (email, phone normalization)
* Website validation logic
* Deduplication logic
* Extraction strategies (structured data, regex)

## Test Style

* Unit tests for logic (pytest)
* Integration tests for workers
* No UI tests required in MVP
* Test fixtures: static HTML files for scraper tests

## Tools

* pytest + pytest-asyncio
* ruff (linter)
* mypy (type checker)

---

# CODE QUALITY RULES

* No duplicate logic
* No magic numbers (use constants)
* No hidden dependencies
* No circular imports
* No global mutable state
* All imports at top of file (no inline imports except lazy-loaded optional deps)

---

# REFACTOR RULES

If a function exceeds:

* 50 lines → refactor
* 3 responsibilities → split service
* 5 parameters → use a dataclass/typed dict
* 3 levels of nesting → simplify

---

# DEFINITIONS OF DONE

A module is complete only if:

* [x] It is tested
* [x] It is documented
* [x] It is deterministic
* [x] It is idempotent (if worker)
* [x] It follows folder structure
* [x] It does not break existing contracts
* [x] ruff lint passes (ruff check)
* [x] ruff format passes

---

# FINAL RULES

If unsure how to implement something:

> Prefer simplicity over optimization
> Prefer clarity over abstraction
> Prefer deterministic behavior over "smart" logic

When accessing ORM attributes in workers:

> Extract fields to local variables immediately after loading to prevent MissingGreenlet errors
