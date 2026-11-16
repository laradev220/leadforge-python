# LeadForge AI

> **Queue-driven enrichment pipeline** — Discover, enrich, score, and export business leads at scale.

LeadForge is a modular, async Python platform that scrapes business data from Google Maps, directories, and websites, enriches it with contact/social information, scores leads by quality, and exports the results. All long-running work is delegated to distributed Arq workers connected via Redis queues.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Running the API](#running-the-api)
- [Running Workers](#running-workers)
- [Database Migrations](#database-migrations)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Development](#development)
- [Testing](#testing)

---

## What It Does

LeadForge automates the entire lead generation pipeline:

1. **Discovery** — Search Google Maps, Yelp, and directories by keyword + location to find businesses
2. **Website Analysis** — Visit discovered business websites, analyze SEO, mobile-friendliness, and SSL
3. **Contact Extraction** — Extract emails, phones, and contact forms from websites and social profiles
4. **Social Profile Discovery** — Find and analyze Facebook, Instagram, LinkedIn, and other social profiles
5. **Lead Scoring** — Score each lead (A+ through F) based on website quality, social activity, contact availability, and business validation
6. **Export** — Export qualified leads as CSV, JSON, or XLSX with optional filters

---

## Architecture

```
                    ┌─────────────────────┐
                    │   FastAPI (API)      │
                    │  /api/v1/* routes    │
                    └────────┬────────────┘
                             │ HTTP
                             ▼
┌────────────────────────────────────────────────┐
│              PostgreSQL (Source of Truth)       │
│  users │ search_jobs │ businesses │ leads │ ... │
└────────────────────────────────────────────────┘
         ▲                                   │
         │                              ┌────┴────┐
         │                              │  Redis  │
         │                              │  (Arq)  │
         │                              └────┬────┘
         │                                   │
         ▼                                   ▼
┌──────────────────────────────────────────────────────┐
│                   Workers (Arq Consumers)             │
│                                                        │
│  discovery_worker  ──►  website_worker  ──►  contact_worker│
│                                                    │
│  social_worker  ──►  scoring_worker  ──►  export_worker│
└──────────────────────────────────────────────────────┘
```

### Key Design Rules

- **API never scrapes** — The API creates jobs and reads the database only
- **Workers never expose HTTP** — Workers consume queue jobs and update the database
- **All long-running work goes through queues** — No synchronous heavy processing in the API
- **Database is the source of truth** — Everything is written to PostgreSQL, workers communicate via DB state
- **Each worker is stateless and idempotent** — Workers can be restarted or scaled safely

### Recent Fixes (June 2026)

## Tech Stack

| Layer | Technology |
|---|---|
| **Web Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Migrations** | Alembic |
| **Queue** | Arq (Redis-backed) |
| **HTTP Client** | httpx |
| **HTML Parsing** | selectolax + BeautifulSoup4 |
| **Browser Automation** | Playwright (async, human-like motion) |
| **Validation** | Pydantic v2 |
| **Logging** | structlog |
| **Configuration** | pydantic-settings |
| **Authentication** | PyJWT + bcrypt |
| **Testing** | pytest + pytest-asyncio |
| **Package Manager** | uv (workspaces) |

---

## Prerequisites

- **Python 3.12+** (see `.python-version`)
- **PostgreSQL 15+** (running on localhost:5433 or configured via `DATABASE_URL`)
- **Redis 7+** (running on localhost:6379 or configured via `REDIS_HOST`/`REDIS_PORT`)
- **Chrome/Chromium** (for Playwright-based scraping)
- **uv** — Python package manager

### Installing uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Installing Playwright

```bash
uv run playwright install chromium
```

---

## Quick Start

### 1. Clone and install dependencies

```bash
git clone <repo-url> leadforge
cd leadforge
uv sync
```

### 2. Start infrastructure

```bash
# Using Docker (recommended for development)
docker compose -f infra/docker/docker-compose.yaml up -d postgres redis

# Or start PostgreSQL and Redis directly on their default ports
```

### 3. Configure environment

Copy the example configuration or set environment variables:

```bash
# Create .env file (optional — defaults work for local dev)
cat > .env << 'EOF'
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/leadforge
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5433/leadforge
REDIS_HOST=localhost
REDIS_PORT=6379
JWT_SECRET=change-me-in-production
EXPORT_DIR=./exports
EOF
```

### 4. Run database migrations

```bash
uv run --package leadforge-database alembic upgrade head
```

### 5. Start the API

```bash
uv run --package api uvicorn leadforge_api.main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.

### 6. (Optional) Start a worker

```bash
# Start the export worker (useful for testing export functionality)
uv run --package export-worker python -m leadforge_export_worker

# Start the discovery worker
uv run --package discovery-worker python -m leadforge_discovery_worker
```

### 7. Test with the API

```bash
# Health check
curl http://localhost:8000/health

# Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123","fullName":"Test User"}'

# Login (save the token)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'

# Use the token for authenticated requests
curl http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <your-token>"
```

### 8. Import Postman Collection

Import `postman/LeadForge.postman_collection.json` into Postman for a full set of pre-configured requests with auth handling.

---

## Configuration

All configuration is managed via environment variables (with sensible defaults). See `packages/config/src/leadforge_config/settings.py`.

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@localhost:5433/leadforge` | Async DB connection |
| `DATABASE_URL_SYNC` | `postgresql://postgres:postgres@localhost:5433/leadforge` | Sync DB connection |
| `REDIS_HOST` | `localhost` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `JWT_SECRET` | `dev-secret` | JWT signing key (change in production!) |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRES_HOURS` | `24` | Token expiration |
| `EXPORT_DIR` | `./exports` | Export file storage directory |
| `SCRAPER_CONCURRENCY` | `3` | Max concurrent scrapes |
| `SCRAPER_REQUEST_DELAY_MS` | `2000` | Delay between requests (ms) |
| `SCRAPER_REQUEST_TIMEOUT_MS` | `10000` | Request timeout (ms) |
| `PLAYWRIGHT_HEADLESS` | `true` | Run Playwright in headless mode |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_JSON` | `true` | JSON-format logs |
| `ENABLED_SOURCES` | (empty) | Comma-separated list of source labels |

---

## Running the API

```bash
# Development (with auto-reload)
uv run --package api uvicorn leadforge_api.main:app --reload --host 0.0.0.0 --port 8000

# Production
uv run --package api uvicorn leadforge_api.main:app --host 0.0.0.0 --port 8000 --workers 4

# Or use the built-in runner
uv run --package api python -c "from leadforge_api.main import run; run()"
```

### API Endpoints Overview

All endpoints are prefixed with `/api/v1`.

### Google Maps Extraction — How It Works

The Google Maps scraper no longer opens place pages in new tabs (those pages load phone/rating via protobuf RPC — not accessible from HTML/DOM). Instead:

1. **Scroll** the search results feed with human-like motion
2. **Extract metadata** from feed items via ARIA labels: name, rating (`"4.5 stars"`), address, category
3. **Click each feed item** to open the side panel (Playwright locator auto-scrolls into view)
4. **Extract phone, website, review_count** from the side panel DOM (loaded via XHR, rendered into DOM)
5. **Close** the panel with Escape key, repeat for next result

This approach reliably captures phone numbers and websites from Google Maps without requiring CSS selectors or protobuf parsing.

| Group | Prefix | Auth | Description |
|---|---|---|---|
| **Auth** | `/auth` | Mixed | Register, login, get current user |
| **Search Jobs** | `/search-jobs` | JWT | Create and manage discovery jobs |
| **Businesses** | `/businesses` | JWT | List, get, re-enrich businesses |
| **Leads** | `/leads` | JWT | List and get scored leads |
| **Analytics** | `/analytics` | JWT | Dashboard stats and lead distribution |
| **Exports** | `/exports` | JWT | Create, list, and download exports |
| **Social Profiles** | `/social-profiles` | JWT | Get social profile by ID |
| **Scrapers** | `/scrapers` | Mixed | Health, metrics (public); cache mgmt (admin) |
| **Admin** | `/admin` | Admin | Queue stats and retry failed jobs |
| **System** | `/health`, `/metrics` | None | Health check and Prometheus metrics |

---

## Verification

Every lead can be checked before export. Verification is queue-driven and
records per-field provenance (source, first seen, last checked).

```bash
# Default: MX/domain check (works offline; reported as "domain-checked")
EMAIL_VERIFIER_PROVIDER=mx
VERIFY_TIMEOUT_MS=10000
VERIFY_MAX_AGE_DAYS=30

# Mailbox-level checks (requires outbound port 25 or a provider key)
# EMAIL_VERIFIER_PROVIDER=smtp
# EMAIL_VERIFIER_PROVIDER=zerobounce
# ZEROBOUNCE_API_KEY=...
```

- `POST /api/v1/businesses/{id}/verify?force=true` re-checks one lead.
- `POST /api/v1/businesses/verify` bulk-checks a filtered segment (max 500).
- `verified_email=true` filters leads whose email passed mailbox-level checks.
- Exports exclude suppressed contacts and (by default) unverified emails.

## Running Workers

Each worker is a separate service that consumes from a specific Arq queue.

```bash
# Discovery — searches Google Maps, directories for businesses
uv run --package discovery-worker python -m leadforge_discovery_worker

# Website — analyzes business websites
uv run --package website-worker python -m leadforge_website_worker

# Contact — extracts contact info from websites
uv run --package contact-worker python -m leadforge_contact_worker

# Social — discovers and analyzes social profiles
uv run --package social-worker python -m leadforge_social_worker

# Verification — checks email deliverability and phone line types
uv run --package verification-worker python -m leadforge_verification_worker

# Scoring — scores leads based on enrichment data
uv run --package scoring-worker python -m leadforge_scoring_worker

# Export — generates export files (CSV, JSON, XLSX)
uv run --package export-worker python -m leadforge_export_worker
```

**Pipeline Flow:**

```
Search Job Created
    │
    ▼
Discovery Worker ──► SearchJobBusiness records
    │
    ▼
Website Worker ──► Website record
    │
    ├────► Contact Worker ──► Contact records
    │
    └────► Social Worker ──► SocialProfile records
    │
    ▼
Verification Worker ──► verification status + provenance
    │
    ▼
Scoring Worker ──► LeadScore record
    │
    ▼
Export Worker ──► CSV / JSON / XLSX file
```

---

## Database Migrations

Migrations are managed with Alembic and live in `packages/database/alembic/`.

```bash
# Run pending migrations
uv run --package leadforge-database alembic upgrade head

# Create a new migration (auto-generate from model changes)
uv run --package leadforge-database alembic revision --autogenerate -m "description of change"

# Rollback one migration
uv run --package leadforge-database alembic downgrade -1

# View migration history
uv run --package leadforge-database alembic history

# Show current migration
uv run --package leadforge-database alembic current
```

---

## API Documentation

### Response Format

All API responses follow a consistent envelope:

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 100,
    "totalPages": 2
  }
}
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "context": { "errors": [...] }
  }
}
```

### Authentication

Most endpoints require a JWT Bearer token:
```
Authorization: Bearer <jwt-token>
```

Get a token via `POST /api/v1/auth/login` or `POST /api/v1/auth/register`.

### Pagination

Paginated endpoints accept `page` (default: 1) and `limit` (default: 50, max: 100) query parameters.

The response includes a `meta` object with `page`, `limit`, `total`, and `totalPages`.

### HTTP Status Codes

| Code | Description |
|---|---|
| `200` | Success |
| `201` | Created |
| `400` | Bad Request |
| `401` | Unauthorized (missing/invalid token) |
| `403` | Forbidden (insufficient role) |
| `404` | Not Found |
| `409` | Conflict |
| `422` | Validation Error |
| `500` | Internal Server Error |

### Complete API Reference

See [`docs/docs/API_SPEC.md`](docs/docs/API_SPEC.md) for the full API specification with all endpoints, request/response schemas, and examples.

---

## Project Structure

```
leadforge/
├── apps/
│   └── api/                          # FastAPI application
│       └── src/leadforge_api/
│           ├── main.py               # App entrypoint, lifespan, exception handlers
│           ├── routes/               # API route handlers (thin controllers)
│           │   ├── auth.py
│           │   ├── search_jobs.py
│           │   ├── businesses.py
│           │   ├── leads.py
│           │   ├── analytics.py
│           │   ├── exports.py
│           │   ├── social_profiles.py
│           │   ├── scrapers.py
│           │   └── admin.py
│           ├── services/             # Business logic layer
│           ├── schemas/              # Pydantic request/response models
│           └── core/                 # Shared utilities
│               ├── deps.py           # FastAPI dependencies (auth, DB session)
│               ├── security.py       # JWT + password hashing
│               ├── errors.py         # Error types + exception handlers
│               ├── response.py       # Standard response envelope
│               ├── pagination.py     # Pagination utilities
│               └── queue.py          # Arq producer (enqueue jobs)
│
├── workers/                          # Arq worker services
│   ├── discovery_worker/             # Google Maps / directory discovery
│   ├── website_worker/               # Website analysis
│   ├── contact_worker/               # Contact extraction
│   ├── social_worker/                # Social profile discovery
│   ├── scoring_worker/               # Lead scoring
│   └── export_worker/                # File export generation
│
├── packages/                         # Shared libraries
│   ├── config/                       # pydantic-settings configuration
│   ├── shared/                       # Types, constants, scoring engine, utilities
│   ├── database/                     # SQLAlchemy models + Alembic migrations
│   ├── worker_core/                  # Arq worker base class + utilities
│   └── scraper_core/                 # Scraping engine (httpx, Playwright)
│
├── tests/                            # Test suite
│   ├── unit/                         # Unit tests
│   └── integration/                  # Integration tests
│
├── infra/docker/                     # Docker Compose for dev infrastructure
├── docs/docs/                        # Project documentation
├── postman/                          # Postman collection
└── pyproject.toml                    # Root workspace config (uv)
```

---

## Development

### Code Quality

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type check
uv run pyright
```

### Adding a New Package

```bash
# Create a new workspace package
mkdir -p packages/my_package/src/leadforge_my_package
# Add pyproject.toml with proper workspace config
uv sync
```

### Verification

Every lead can be checked before export. Verification is queue-driven and
records per-field provenance (source, first seen, last checked).

```bash
# Default: MX/domain check (works offline; reported as "domain-checked")
EMAIL_VERIFIER_PROVIDER=mx
VERIFY_TIMEOUT_MS=10000
VERIFY_MAX_AGE_DAYS=30

# Mailbox-level checks (requires outbound port 25 or a provider key)
# EMAIL_VERIFIER_PROVIDER=smtp
# EMAIL_VERIFIER_PROVIDER=zerobounce
# ZEROBOUNCE_API_KEY=...
```

- `POST /api/v1/businesses/{id}/verify?force=true` re-checks one lead.
- `POST /api/v1/businesses/verify` bulk-checks a filtered segment (max 500).
- `verified_email=true` filters leads whose email passed mailbox-level checks.
- Exports exclude suppressed contacts and (by default) unverified emails.

## Running Workers in Development

For local development with all workers:

```bash
# Terminal 1: Infrastructure
docker compose -f infra/docker/docker-compose.yaml up postgres redis

# Terminal 2: API
uv run --package api uvicorn leadforge_api.main:app --reload --port 8000

# Terminal 3: Workers (run one or more)
uv run --package discovery-worker python -m leadforge_discovery_worker
uv run --package export-worker python -m leadforge_export_worker

# Terminal 4: Test with curl or Postman
curl http://localhost:8000/health
```

---

## Testing

```bash
# Run all tests
uv run pytest

# Run unit tests only
uv run pytest tests/unit/

# Run integration tests only
uv run pytest tests/integration/

# Run tests with coverage
uv run pytest --cov --cov-report=term-missing

# Run specific test file
uv run pytest tests/unit/test_scoring.py -v
```

### Test Fixtures

Test fixtures are in `tests/unit/fixtures/` and `tests/integration/fixtures/`. They include sample HTML pages from Google Maps, Yelp, and business websites for testing extraction logic without live network calls.

---

## Security Notes

- Change `JWT_SECRET` to a strong, unique value in production
- The API enforces JWT authentication on all business/lead/export/analytics endpoints
- Admin endpoints (cache management, queue management) require the `ADMIN` role
- CORS is configured to allow all origins — restrict in production
- Passwords are hashed with bcrypt (12 rounds)
- Never expose the API directly to the internet without a reverse proxy (e.g., nginx, Caddy) + rate limiting
