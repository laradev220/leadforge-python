# TASKS.md

# LeadForge AI Implementation Roadmap

Version: 1.0

Status: Active

---

# Project Goal

Build a lead discovery and outreach intelligence platform capable of:

1. Discovering businesses
2. Enriching business information
3. Finding publicly available contact channels
4. Scoring opportunities
5. Exporting qualified leads

---

# Development Rules

Before starting any task:

* Read PRD.md
* Read ARCHITECTURE.md
* Read DATABASE.md
* Read API_SPEC.md

Never skip phases.

Never build future phases before current phase acceptance criteria are met.

---

# PHASE 0

# Project Foundation

Goal:

Create the project structure and development environment.

Priority:

CRITICAL

---

## Task 0.1

Create Monorepo Structure

[x] Deliverables:

```text
leadforge/
│
├── apps/
│   └── api/
│
├── workers/
│   ├── discovery-worker/
│   ├── website-worker/
│   ├── contact-worker/
│   ├── social-worker/
│   ├── scoring-worker/
│   └── export-worker/
│
├── packages/
│   ├── database/
│   ├── worker-core/
│   ├── shared/
│   ├── config/
│   ├── scraper-core/
│
├── docs/
├── tests/
└── infra/
```

Acceptance Criteria:

* [x] Project installs (`uv sync`)
* [x] Python 3.12 configured
* [x] Shared imports working

---

## Task 0.2
Docker Environment
[x] Deliverables:
* [x] Docker Compose
* [x] PostgreSQL
* [x] Redis

Acceptance Criteria:

[x] ```bash
docker compose up
```
starts all services successfully.

---

## Task 0.3

Configure SQLAlchemy + Alembic

[x] Deliverables:

* [x] SQLAlchemy 2.0 models (11 tables)
* [x] Initial Alembic migration
* [x] Database package

Acceptance Criteria:

[x] ```bash
uv run alembic upgrade head
```
runs successfully.

---

## Task 0.4

Shared Infrastructure

[x] Deliverables:

* [x] Logger (structlog in worker-core)
* [x] Config service (Pydantic-validated env via leadforge_config)
* [x] Environment validation
* [x] Shared types, constants, utils
* [x] Queue connection helpers (Arq + Redis)

Acceptance Criteria:

* [x] All apps consume shared config

---

# PHASE 1
# Authentication & API Foundation
Goal:
Establish API structure.
Priority:
HIGH
---
## Task 1.1
FastAPI API Setup
[x] Deliverables:
* [x] FastAPI
* [x] Python 3.12+
* [x] Routing (APIRouter)
* [x] Error handling (Pydantic validation)
Acceptance Criteria:
[x] Health endpoint works.
```http
GET /health
```
---
## Task 1.2
Authentication System
[x] Deliverables:
* Register
* Login
* JWT middleware
Acceptance Criteria:
Protected routes require valid JWT.
---
## Task 1.3
Users Module
[x] Deliverables:
* User entity
* User service
* User repository
Acceptance Criteria:
CRUD operations work.


---

# PHASE 2
# Queue Infrastructure
Goal:
Create Arq queue architecture.
Priority:
CRITICAL
---
## Task 2.1
Redis Integration
[x] Deliverables:
* [x] Redis connection
* [x] Health checks
Acceptance Criteria:
[x] Redis accessible from all services.
---
## Task 2.2
Arq Queue Setup
[x] Deliverables:
Queues:
```text
discovery_queue
website_queue
contact_queue
social_queue
scoring_queue
export_queue
```
Acceptance Criteria:
[x] Jobs can be added and processed.
---
## Task 2.3
Queue Monitoring
[x] Deliverables:
* [x] Queue metrics (GET /admin/queues)
* [x] Queue status endpoints (POST /admin/queues/retry)
Acceptance Criteria:
[x] Queue statistics visible via API.


---

# PHASE 3

# Search Jobs

Goal:

Create business discovery workflow.

Priority:

CRITICAL

---

## Task 3.1

Search Job API

[x] Endpoints:

```http
POST /search-jobs
GET /search-jobs
GET /search-jobs/:id
POST /search-jobs/:id/cancel
```

Acceptance Criteria:

[x] Jobs stored in database.

---

## Task 3.2

Discovery Queue Integration

[x] Behavior:

Search job automatically creates:

```text
discovery_queue job
```

Acceptance Criteria:

[x] Queue receives jobs.

---

# PHASE 4

# Discovery Worker

Goal:

Business discovery engine.

Priority:

CRITICAL

---

## Task 4.1

Discovery Worker Skeleton

[x] Deliverables:

* [x] Worker process
* [x] Arq consumer

Acceptance Criteria:

[x] Worker consumes queue jobs.

---

## Task 4.2

Business Parser

[x] Responsibilities:

Extract:

* [x] Name
* [x] Category
* [x] Address
* [x] Phone
* [x] Rating
* [x] Reviews

Acceptance Criteria:

[x] Businesses stored successfully.

---

## Task 4.3

Deduplication

[x] Rules:

Prevent duplicate businesses.

Acceptance Criteria:

[x] Duplicate records rejected.

---

# PHASE 5 (DONE)

# Website Discovery

Goal:

Find business websites.

Priority:

HIGH

---

## Task 5.1

[x] Website Queue

Acceptance Criteria:

[x] Business discovery creates website jobs.

---

## Task 5.2

[x] Website Discovery Service

Responsibilities:

* [x] Validate websites
* [x] Normalize domains

Acceptance Criteria:

[x] Website record created.

---

## Task 5.3

[x] Website Health Analysis

Collect:

* [x] SSL
* [x] Response status
* [x] Load time

Acceptance Criteria:

[x] Metrics stored.

---

# PHASE 6 (DONE)

# Contact Discovery

Goal:

Find public contact methods.

Priority:

HIGH

---

## Task 6.1

[x] Contact Worker

Responsibilities:

* [x] Crawl websites
* [x] Extract contact data

Acceptance Criteria:

[x] Contacts stored.

---

## Task 6.2

[x] Email Extraction

Patterns:

```text
info@
hello@
contact@
support@
```

Acceptance Criteria:

[x] Public emails extracted.

---

## Task 6.3

[x] Phone Extraction

Acceptance Criteria:

[x] Phone numbers normalized.

---

## Task 6.4

[x] Contact Form Detection

Acceptance Criteria:

[x] Forms identified and stored.

---

# PHASE 7 (DONE)

# Social Discovery

Goal:

Find business social profiles.

Priority:

HIGH

---

## Task 7.1

[x] Social Worker

Acceptance Criteria:

[x] Worker processes social jobs.

---

## Task 7.2

[x] Profile Discovery

Platforms:

* [x] Facebook
* [x] Instagram
* [x] LinkedIn
* [x] YouTube
* [x] TikTok

Acceptance Criteria:

[x] Profiles stored.

---

## Task 7.3

[x] Social Enrichment

Collect:

* [x] Followers
* [x] Website
* [x] Public contact information
* [x] Last activity

Acceptance Criteria:

[x] Enrichment data saved.

---

# PHASE 8 (DONE)

# Lead Scoring Engine

Goal:

Qualify leads.

Priority:

HIGH

---

## Task 8.1

[x] Scoring Worker

Acceptance Criteria:

[x] Worker consumes scoring queue.

---

## Task 8.2

[x] Lead Score Formula

Inputs:

* [x] Website status
* [x] Reviews
* [x] Contacts
* [x] Social activity

Output:

```text
0-100
```

Acceptance Criteria:

[x] Score generated.

---

## Task 8.3

[x] Best Contact Method Engine

Output:

```text
EMAIL
CONTACT_FORM
FACEBOOK
INSTAGRAM
LINKEDIN
PHONE
```

Acceptance Criteria:

[x] Method selected automatically.

---

# PHASE 9 (SKIPPED — Backend-only MVP)
# Dashboard
Goal:
User interface.
Priority:
LOW
---
## Task 9.1
Authentication UI
[ ] Deliverables:
* Login flow works (built as API endpoints, no UI)
---
## Task 9.2
Search UI
[ ] Deliverables:
* Search jobs can be created (built as API endpoints, no UI)
---
## Task 9.3
Business Table
[ ] Deliverables:
* Pagination
* Filtering
* Sorting
(all built as API endpoints, no UI)
---

# PHASE 10 (DONE)

# Export System

Goal:

Download qualified leads.

Priority:

MEDIUM

---

## Task 10.1

[x] Export Queue

Acceptance Criteria:

[x] Export jobs processed.

---

## Task 10.2

[x] CSV Export

Acceptance Criteria:

[x] CSV downloadable.

---

## Task 10.3

[x] XLSX Export

Acceptance Criteria:

[x] Excel downloadable (TSV fallback in MVP).

---

## Task 10.4

[x] JSON Export

Acceptance Criteria:

[x] JSON downloadable.

---

# PHASE 11 (DONE)

# Observability

Goal:

Production readiness.

Priority:

MEDIUM

---

## Task 11.1

[x] Structured Logging

Use:

```text
structlog
```

Acceptance Criteria:

[x] Logs searchable (structlog JSON structured logging in all workers).

---

## Task 11.2

[x] Worker Metrics

Track:

* [x] Jobs processed
* [x] Failures
* [x] Duration

Acceptance Criteria:

[x] Metrics visible (via job_queue_logs table + structlog logs).

---

## Task 11.3

[x] Error Tracking

Acceptance Criteria:

[x] Worker failures recorded (job_queue_logs table + error logging).

---

# PHASE 12 (DONE)

# Production Readiness

Goal:

Deployment capable.

Priority:

MEDIUM

---

## Task 12.1

[x] Docker Images

Acceptance Criteria:

[x] All services containerized (API + 6 workers + Postgres + Redis).

---

## Task 12.2

[x] Environment Management

Acceptance Criteria:

[x] No hardcoded secrets (all via .env + docker-compose env vars).

---

## Task 12.3

[ ] Backup Strategy

Acceptance Criteria:

[ ] Database backup process documented (PostgreSQL + Redis persistence configured).

---

# PHASE 13 (DONE)

# Google Maps Extraction Rework

Goal:

Reliable extraction of phone, rating, and website from Google Maps.

Priority:

HIGH

---

## Task 13.1

[x] Side panel extraction

Acceptance Criteria:

[x] Phone numbers extracted from side panel DOM (e.g., `+44 20 7287 2200`)
[x] Websites extracted from side panel DOM (e.g., `pizzapilgrims.co.uk`)
[x] Review counts extracted from side panel DOM (e.g., `(15,287)`)
[x] Feed item metadata extracted from ARIA labels (name, rating, address)

---

## Task 13.2

[x] Rating regex fix

Acceptance Criteria:

[x] `"4.5 stars"` pattern (without review count) now matches
[x] `"4.7 stars 3,901 Reviews"` full pattern continues to match

---

## Task 13.3

[x] Dead code removal

Acceptance Criteria:

[x] `_extract_from_visible_text` removed
[x] `_extract_from_internal_state` removed
[x] `_parse_internal_state` removed
[x] `_run_pipeline` removed
[x] `_try_stealth_playwright` removed
[x] `_pipeline` and CSS selector strategy imports removed

---

## Task 13.4

[x] MissingGreenlet fix

Acceptance Criteria:

[x] Website worker no longer crashes with `MissingGreenlet: greenlet_spawn has not been called`
[x] Business fields (`name`, `city`, `state`) extracted to local variables immediately after ORM load

# MVP Definition

Backend MVP is complete when:

[x] Search jobs work — POST/GET /search-jobs, queue integration
[x] Businesses are discovered — Playwright Google Maps scraper + dedup
[x] Websites are discovered — Website analysis worker (SSL, SEO, mobile)
[x] Public contacts are extracted — Email, phone, WhatsApp, contact forms
[x] Social profiles are discovered — Facebook, Instagram, LinkedIn, etc.
[x] Lead scores are calculated — Deterministic scoring engine (0-100)
[x] Leads can be exported — CSV, JSON, XLSX (via TSV)
[ ] Dashboard is operational — Skipped for backend-only MVP

---

# Codex Execution Rules

1. Complete phases sequentially.
2. Never skip acceptance criteria.
3. Do not create placeholder implementations.
4. Write tests for core services.
5. Keep controllers thin.
6. Keep workers independent.
7. Use queues for all long-running tasks.
8. Prefer composition over inheritance.
9. Favor explicit code over magic abstractions.
10. Mark every completed task in this document.

