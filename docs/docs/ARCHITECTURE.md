# LeadForge AI Architecture

Version: 2.0

Status: Approved for MVP

---

# Architecture Principles

LeadForge AI is designed as a:

**Modular Monolith + Distributed Workers**

The platform is intentionally NOT built as microservices.

Reasons:

* Faster development
* Easier debugging
* Simpler deployment
* Lower operational cost
* Easier AI-assisted development
* Easier database management

Workers scale independently through Arq (Redis-backed queues).

---

# Technology Stack

## Backend

```text
Python 3.12+
FastAPI (async)
SQLAlchemy 2.0 (async ORM)
Alembic (migrations)
Pydantic v2 (validation)
```

---

## Data Layer

```text
PostgreSQL 15+
Redis 7+
```

---

## Queue Layer

```text
Arq (Redis-backed)
Redis
```

Arq is the backbone of all scraping and enrichment operations.

Redis acts as the single source of truth for queue state.

---

## Scraping Layer

```text
Playwright (async, human-like motion)
httpx (HTTP client)
selectolax + BeautifulSoup4 (HTML parsing)
```

Playwright:

* Dynamic websites
* Google Maps navigation (side panel extraction)
* JavaScript-heavy pages

selectolax + BeautifulSoup4:

* Fast HTML parsing
* Contact extraction
* Link discovery

---

## Observability

```text
structlog (structured logging)
```

---

## Configuration

```text
pydantic-settings (env-driven config)
```

---

## Infrastructure

```text
Docker
Docker Compose
uv (Python package manager)
```

---

# System Architecture

```text
                    curl / Postman
                        │
                        ▼
                  FastAPI (Port 8000)
                        │
                        ▼
                  PostgreSQL (5433)
                        ▲
                        │
────────────────────────┼────────────────────────
                        │
                        ▼
                  Redis (6379)
                        │
                        ▼
                  Arq Queues
                        │
        ┌───────────────┼───────────────┐
        │               │               │
        ▼               ▼               ▼

 Discovery      Enrichment      Export Worker
  Worker           Worker

        │
        ▼

 Website Worker

        │
        ▼

 Contact Worker

        │
        ▼

 Social Worker

        │
        ▼

 Scoring Worker
```

---

# Architecture Philosophy

API servers never scrape.

API servers only:

* Create jobs
* Read results
* Manage users
* Export data

All scraping runs in workers.

This prevents:

* Request timeouts
* Memory spikes
* API crashes

---

# Core Workflow

## Search Creation

User submits:

```json
{
  "keyword": "Dentist",
  "location": "Houston"
}
```

API creates:

```text
Search Job (PostgreSQL)
```

Queue:

```text
arq:queue:discovery
```

---

# Queue Pipeline

The entire platform operates as a pipeline.

```text
Discovery
    ↓
Website Discovery
    ↓
Website Crawl
    ↓
Contact Discovery
    ↓
Social Discovery
    ↓
Lead Scoring
    ↓
Export
```

Each step has:

* independent retries (3 attempts, exponential backoff)
* independent concurrency
* independent monitoring

---

# Queue Definitions

## discovery (queue)

Purpose:

Find businesses from Google Maps and directories.

Input:

```json
{
  "searchJobId": "uuid",
  "keyword": "Restaurant",
  "location": "London"
}
```

Output:

Business records created in PostgreSQL.

Creates:

```text
arq:queue:website
```

---

## website (queue)

Purpose:

Discover and validate business website.

Input:

```json
{
  "business_id": "uuid"
}
```

Output:

Website record with SSL, HTTP status, load time, SEO score.

Creates:

```text
arq:queue:contact
```

---

## contact (queue)

Purpose:

Extract contact information from website.

Collect:

* emails
* contact forms
* phones
* whatsapp links

Creates:

```text
arq:queue:social
```

---

## social (queue)

Purpose:

Discover social profiles.

Collect:

* Facebook
* Instagram
* LinkedIn
* YouTube
* TikTok

Creates:

```text
arq:queue:scoring
```

---

## scoring (queue)

Purpose:

Calculate lead score.

Input:

Website, contacts, social profiles, reviews.

Output:

```json
{
  "score": 85,
  "bestContactMethod": "EMAIL"
}
```

---

## export (queue)

Purpose:

Generate:

* CSV
* XLSX
* JSON

---

# Worker Architecture

Each worker runs independently as a separate Python process via Arq.

```text
workers/
├── discovery_worker/
├── website_worker/
├── contact_worker/
├── social_worker/
├── scoring_worker/
├── export_worker/
```

Workers are separate processes.

Arq supports distributed workers safely using Redis coordination.

Worker startup:

```bash
uv run --package <worker-name> python -m leadforge_<worker>_worker
```

---

# Discovery Worker

Responsibilities:

* Search Google Maps (side panel extraction) and directories
* Collect business listings
* Deduplicate businesses
* Normalize phone, website, address

Must never:

* Crawl websites
* Extract contacts

Single responsibility only.

---

# Website Worker

Responsibilities:

* Website discovery (search engine fallback)
* Website validation (SSL, HTTP status, reachable)
* SEO and mobile-friendliness scoring

Checks:

```text
Website Exists
SSL Enabled
Website Reachable
Load Time
Mobile Friendly
SEO Score
```

---

# Contact Worker

Responsibilities:

Extract:

```text
Email
Phone
Contact Form
WhatsApp
```

Search locations:

```text
Homepage
Footer
Contact Page
About Page
Privacy Policy
Terms
```

---

# Social Worker

Responsibilities:

Discover:

```text
Facebook
Instagram
LinkedIn
YouTube
TikTok
```

Enrich:

```text
Followers
Bio
Website
Activity
```

Only public information.

---

# Scoring Worker

Purpose:

Generate lead intelligence.

Inputs:

```text
Website Status
Reviews
Ratings
Contacts
Social Activity
```

Outputs:

```json
{
  "score": 0,
  "grade": "C",
  "bestContactMethod": ""
}
```

---

# Database Access Rules

Workers may:

* read database
* write database

Workers must never:

* perform schema migrations

Only API service owns migrations (via Alembic).

---

# Codes Structure

Shared packages:

```text
packages/
├── config/          # pydantic-settings configuration
├── shared/          # Types, constants, scoring engine, utilities
├── database/        # SQLAlchemy models + Alembic migrations
├── worker_core/     # Arq worker wrapper + queue helpers
└── scraper_core/    # Scraping engine (Playwright, httpx, extraction)
```

Imported by:

* API
* Workers

Single source of truth.

---

# Logging

Required:

```text
structlog
```

Every job must log:

```json
{
  "jobId": "",
  "worker": "",
  "duration": "",
  "status": ""
}
```

Logs are structured JSON by default (`LOG_JSON=true`).

---

# Error Handling

Every worker:

```text
attempts: 3
```

Backoff:

```text
Exponential jitter (2s initial, 30s max)
```

Arq automatically moves failed jobs into failed state.

---

# Idempotency

Every worker must be idempotent.

Running the same job twice must not create duplicate businesses.

Use:

```text
Unique Constraints (external_id)
Upserts
Deterministic Keys
```

---

# Rate Limiting

Required.

Never allow unlimited scraping.

Implement:

```text
Concurrency Limits (SCRAPER_CONCURRENCY env)
Request Delays (SCRAPER_REQUEST_DELAY_MS env)
Worker Throttling
Circuit Breakers (per source, exponential retry)
```

Queue concurrency configurable through environment variables.

---

# Scaling Strategy

## Phase 1

```text
1 API (FastAPI)
1 PostgreSQL
1 Redis
1 Worker Node
```

## Phase 2

```text
1 API
1 PostgreSQL
1 Redis
3 Discovery Workers
3 Website Workers
3 Contact Workers
3 Social Workers
```

## Phase 3

Horizontal scaling.

Arq workers can run on multiple machines while Redis coordinates job execution.

---

# Future Architecture

Possible future additions:

```text
AI Lead Summaries
CRM Integrations
Lead Recommendations
Multi-Region Scraping
Observability Stack
```

MVP architecture must remain modular enough to support future extraction into services if required.

---

# Codex Rules

When generating code:

1. Prefer simplicity.
2. Prefer modular monolith.
3. Keep business logic outside controllers.
4. Keep scraping logic inside workers.
5. Never scrape inside API requests.
6. Use queues for all long-running tasks.
7. Every worker must be independently deployable.
8. SQLAlchemy is the only ORM.
9. PostgreSQL is the source of truth.
10. Redis is queue infrastructure only.
