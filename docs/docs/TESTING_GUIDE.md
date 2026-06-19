# TESTING_GUIDE.md

# LeadForge — Testing & Setup Guide

Version: 1.0

Status: Active

---

# 🚀 Quick Start

## Prerequisites

```text
uv (Python package manager)
PostgreSQL 16+
Redis 7+
Playwright Chromium
```

## Step 1 — Start Infrastructure

Start PostgreSQL and Redis via Docker Compose:

```bash
cd infra/docker
docker compose up -d postgres redis
```

Verify they're up:

```bash
pg_isready -h localhost -p 5433     # PostgreSQL on port 5433 (Docker-mapped)
redis-cli ping                       # Should return PONG
```

> **Note:** Docker Compose maps PostgreSQL from port **5433** (host) to
> **5432** (container). The project defaults to port 5433. If you run
> PostgreSQL locally (not via Docker), it's likely on the default port
> **5432** — adjust `.env` and commands accordingly.

---

## Step 2 — Set Up Environment

Copy and review the environment file:

```bash
cp .env.example .env
```

Minimal `.env` for local dev:

```text
NODE_ENV=development

DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/leadforge
DATABASE_URL_SYNC=postgresql://postgres:postgres@localhost:5433/leadforge

REDIS_HOST=localhost
REDIS_PORT=6379

JWT_SECRET=dev-secret-change-in-production

PLAYWRIGHT_HEADLESS=true
PLAYWRIGHT_PROXY_URL=             # Leave blank for local dev
```

Create the database:

```bash
createdb -h localhost -p 5433 -U postgres leadforge
```

---

## Step 3 — Install Dependencies

```bash
make setup
```

This runs:

1. `uv sync` — installs all Python packages
2. `uv pip install -e packages/... apps/... workers/...` — installs local packages in editable mode
3. `uv run playwright install chromium` — downloads Playwright Chromium
4. `alembic upgrade head` — applies all database migrations

If `make setup` completes without errors, you're ready.

---

## Step 4 — Start Services

### Start the API

```bash
make run-api
```

The API starts at **http://localhost:8000**.

Verify:

```bash
curl http://localhost:8000/health
# → {"success":true,"service":"leadforge-api"}
```

---

### Start Workers (in separate terminals)

Open 6 terminals and run each worker in its own terminal:

```bash
# Terminal 1 — Discovery Worker
make run-discovery-worker

# Terminal 2 — Website Worker
make run-website-worker

# Terminal 3 — Contact Worker
make run-contact-worker

# Terminal 4 — Social Worker
make run-social-worker

# Terminal 5 — Scoring Worker
make run-scoring-worker

# Terminal 6 — Export Worker
make run-export-worker
```

Or run all in background:

```bash
make run-all-workers
```

Stop all workers:

```bash
make kill-all-workers
```

Stop the API:

```bash
make kill-api
```

---

## Step 5 — Test the Full Flow

### 5a. Health Check

```bash
curl http://localhost:8000/health
```

Expected:

```json
{"success":true,"service":"leadforge-api"}
```

---

### 5b. Register a User

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@leadforge.dev","password":"password123","fullName":"Demo User"}'
```

Expected:

```json
{
  "success": true,
  "data": {
    "user": { "id": "...", "email": "demo@leadforge.dev", "full_name": "Demo User", "role": "USER" },
    "token": "eyJ..."
  }
}
```

Save the `token` — you'll use it for all subsequent requests.

---

### 5c. Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@leadforge.dev","password":"password123"}'
```

Expected: Same response format as register. Saves a new token.

---

### 5d. Get Current User

```bash
TOKEN="eyJ..."  # Replace with your token

curl -X GET http://localhost:8000/api/v1/auth/me \
  -H 'Authorization: Bearer $TOKEN'
```

Expected:

```json
{"success":true,"data":{"id":"...","email":"demo@leadforge.dev","full_name":"Demo User","role":"USER","created_at":"..."}}
```

---

### 5e. Create a Search Job

```bash
curl -X POST http://localhost:8000/api/v1/search-jobs \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $TOKEN' \
  -d '{"keyword":"Restaurant","location":"London","country":"GB","radius_km":5}'
```

Expected:

```json
{"success":true,"data":{"job_id":"uuid-here","status":"PENDING"}}
```

Save the `job_id` — you'll use it to track progress.

> **Note:** The `country` field is optional (ISO-3166-1 alpha-2, e.g. US, GB,
> PK). When omitted, the system auto-detects it from the location string via
> OpenStreetMap Nominatim.

---

### 5f. Monitor Search Job Status

```bash
JOB_ID="your-job-id"

curl -X GET http://localhost:8000/api/v1/search-jobs/$JOB_ID \
  -H 'Authorization: Bearer $TOKEN'
```

The status will progress:
- `PENDING` → `RUNNING` → `COMPLETED` (or `FAILED`)

Poll every 10-15 seconds to watch it progress.

---

### 5g. List Search Jobs

```bash
curl -X GET 'http://localhost:8000/api/v1/search-jobs?page=1&limit=50' \
  -H 'Authorization: Bearer $TOKEN'
```

---

### 5h. List Discovered Businesses

Once the search job is `RUNNING` or `COMPLETED`:

```bash
curl -X GET 'http://localhost:8000/api/v1/businesses?page=1&limit=50' \
  -H 'Authorization: Bearer $TOKEN'
```

Optional filters:

```bash
# By country
curl -X GET 'http://localhost:8000/api/v1/businesses?country=GB'

# By category
curl -X GET 'http://localhost:8000/api/v1/businesses?category=Restaurant'

# By website status
curl -X GET 'http://localhost:8000/api/v1/businesses?website_status=FOUND'

# Min rating
curl -X GET 'http://localhost:8000/api/v1/businesses?min_rating=4.0'
```

---

### 5i. Get Business Details

```bash
BUSINESS_ID="your-business-id"

curl -X GET http://localhost:8000/api/v1/businesses/$BUSINESS_ID \
  -H 'Authorization: Bearer $TOKEN'
```

---

### 5j. Check Enriched Data

After workers have processed the business, check:

**Website:**
```bash
curl -X GET http://localhost:8000/api/v1/businesses/$BUSINESS_ID/website \
  -H 'Authorization: Bearer $TOKEN'
```

**Contacts:**
```bash
curl -X GET http://localhost:8000/api/v1/businesses/$BUSINESS_ID/contacts \
  -H 'Authorization: Bearer $TOKEN'
```

**Social Profiles:**
```bash
curl -X GET http://localhost:8000/api/v1/businesses/$BUSINESS_ID/social-profiles \
  -H 'Authorization: Bearer $TOKEN'
```

---

### 5k. View Leads (Scored)

Once the scoring worker has processed:

```bash
curl -X GET 'http://localhost:8000/api/v1/leads?page=1&limit=50' \
  -H 'Authorization: Bearer $TOKEN'
```

Filter by score:

```bash
# High-value leads only
curl -X GET 'http://localhost:8000/api/v1/leads?score_min=80'

# By grade
curl -X GET 'http://localhost:8000/api/v1/leads?grade=A'

# By best contact method
curl -X GET 'http://localhost:8000/api/v1/leads?best_contact_method=EMAIL'
```

---

### 5l. View Dashboard Analytics

```bash
# Dashboard stats (no auth required)
curl -X GET http://localhost:8000/api/v1/analytics/dashboard

# Lead distribution (no auth required)
curl -X GET http://localhost:8000/api/v1/analytics/lead-distribution
```

---

### 5m. Export Leads

Create an export:

```bash
curl -X POST http://localhost:8000/api/v1/exports \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $TOKEN' \
  -d '{"format":"CSV","filters":{"score_min":60}}'
```

Expected:

```json
{"success":true,"data":{"export_id":"uuid-here"}}
```

List your exports:

```bash
curl -X GET http://localhost:8000/api/v1/exports \
  -H 'Authorization: Bearer $TOKEN'
```

Download the file (once the export worker has processed it):

```bash
EXPORT_ID="your-export-id"

curl -X GET http://localhost:8000/api/v1/exports/$EXPORT_ID/download \
  -H 'Authorization: Bearer $TOKEN' \
  -o leads.csv
```

Formats available: `CSV`, `JSON`, `XLSX` (via TSV fallback).

---

### 5n. Admin — Queue Monitoring

> ⚠️ **Requires `ADMIN` role.** A default user has `USER` role. To enable
> admin access, run this in the database:
>
> ```sql
> UPDATE users SET role = 'ADMIN' WHERE email = 'demo@leadforge.dev';
> ```
>
> Then log in again to get a fresh token.

```bash
curl -X GET http://localhost:8000/api/v1/admin/queues \
  -H 'Authorization: Bearer $TOKEN'
```

Shows pending, running, and completed counts for all 6 queues.

Retry all failed jobs:

```bash
curl -X POST http://localhost:8000/api/v1/admin/queues/retry \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer $TOKEN'
```

---

# 🏭 Architecture Overview

```text
                    ┌──────────────┐
                    │  Postman/cURL │
                    └──────┬───────┘
                           │ HTTP
                    ┌──────▼───────┐
                    │  FastAPI      │  Port 8000
                    │  (leadforge)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼───┐  ┌────▼───┐  ┌────▼───┐
         │Postgres│  │ Redis   │  │ Queue   │
         │ 5433   │  │ 6379    │  │(arq)    │
         └────────┘  └─────────┘  └────┬───┘
                                       │
          ┌───────────┬───────────┬─────┼──────┬───────────┬───────────┐
          │           │           │     │      │           │           │
     ┌────▼────┐ ┌───▼───┐ ┌───▼───┐ ┌▼───┐ ┌──▼────┐ ┌───▼────┐
     │Discovery│ │Website│ │Contact│ │Social│ │Scoring│ │ Export │
     │ Worker  │ │Worker │ │Worker │ │Worker│ │Worker │ │ Worker │
     └─────────┘ └───────┘ └───────┘ └─────┘ └───────┘ └────────┘
```

**Pipeline flow:**

```text
Search Job
    │
    ▼
Discovery Worker ──► Google Maps + Directories (businesses found)
    │
    ▼
Website Worker ──► Find & validate website (SSL, HTTP status, SEO)
    │
    ▼
Contact Worker ──► Extract email, phone, WhatsApp, contact forms
    │
    ▼
Social Worker ──► Find Facebook, Instagram, LinkedIn, YouTube, TikTok
    │
    ▼
Scoring Worker ──► Calculate lead score (0-100) + best contact method
    │
    ▼
Export Worker ──► Generate CSV / JSON / XLSX
```

---

# 🔧 Makefile Reference

| Command | Description |
|---|---|
| `make setup` | Full setup: deps + Playwright + DB + migrations |
| `make install-deps` | Install Python packages only |
| `make install-playwright` | Download Playwright Chromium |
| `make db-create` | Create `leadforge-python` database |
| `make db-migrate` | Run Alembic migrations |
| `make run-api` | Start FastAPI on port 8000 |
| `make run-discovery-worker` | Start discovery worker |
| `make run-website-worker` | Start website worker |
| `make run-contact-worker` | Start contact worker |
| `make run-social-worker` | Start social worker |
| `make run-scoring-worker` | Start scoring worker |
| `make run-export-worker` | Start export worker |
| `make run-all-workers` | Start all 6 workers in background |
| `make kill-api` | Stop the API |
| `make kill-all-workers` | Stop all workers |
| `make lint` | Run ruff (linter) |
| `make typecheck` | Run mypy (type checker) |
| `make test` | Run all tests |
| `make test-unit` | Run unit tests only |
| `make test-integration` | Run integration tests only |
| `make clean` | Remove `.venv` and `exports/` |

---

# 🧪 Postman Collection

Import **`postman/LeadForge.postman_collection.json`** into Postman.

## Variables

The collection uses these auto-managed variables:

| Variable | Set By | Description |
|---|---|---|
| `baseUrl` | Manual | Default: `http://localhost:8000` |
| `authToken` | Login / Register | JWT token, auto-stored |
| `userId` | Login / Register | Current user's UUID |
| `searchJobId` | Create Search Job | Most recent job ID |
| `businessId` | List Businesses | First business ID |
| `exportId` | Create Export | Most recent export ID |

## Suggested Test Flow

1. **Health** → `GET /health`
2. **Auth** → `POST Register` (creates user + stores token)
3. **Auth** → `POST Login` (refreshes token)
4. **Auth** → `GET Me` (verify auth works)
5. **Search Jobs** → `POST Create Search Job` (start discovery)
6. **Search Jobs** → `GET Search Job by ID` (poll until COMPLETED)
7. **Businesses** → `GET List Businesses` (see discovered data)
8. **Analytics** → `GET Dashboard Stats` (see system totals)
9. **Leads** → `GET List Leads` (once scored)
10. **Exports** → `POST Create Export` + `GET Download`

---

# ⚠️ Troubleshooting

## API won't start

```bash
# Check PostgreSQL is running
pg_isready -h localhost -p 5433

# Check Redis is running
redis-cli ping

# Check the .env has correct connection strings
cat .env | grep DATABASE_URL
```

## Worker crashes on startup

```bash
# Check for import errors
cd /home/irfan/www/LeadForge-python
.venv/bin/python -c "from leadforge_discovery_worker import main; print('OK')"

# Swap worker name as needed
```

## "Database does not exist"

```bash
createdb -h localhost -p 5433 -U postgres leadforge-python
make db-migrate
```

## "Event loop already running"

Workers run via `.venv/bin/python` (not `uv run`) to avoid this. Check the
Makefile target uses the correct path.

## Migrations not applied

```bash
uv run alembic upgrade head
```

Check migration history:

```bash
uv run alembic history
```

## No businesses found after search job

Possible reasons:

1. No workers running — start them with `make run-all-workers`
2. Google Maps blocked — set `PLAYWRIGHT_PROXY_URL` in `.env`
3. No matching results — try different keywords/locations

## Playwright browser not found

```bash
make install-playwright
# Or manually:
uv run playwright install chromium
```

---

# 🔄 Complete Reset

If you need to start from scratch:

```bash
# 1. Stop everything
make kill-api
make kill-all-workers

# 2. Drop and recreate database
dropdb -h localhost -p 5433 -U postgres leadforge-python
createdb -h localhost -p 5433 -U postgres leadforge-python

# 3. Re-run migrations
make db-migrate

# 4. Restart services
make run-api
make run-all-workers
```

---

# Codex Rules

1. Always verify infrastructure is running before testing.
2. Use Postman collection variables for tokens — never hardcode.
3. Monitor queue stats via `/admin/queues` to track pipeline progress.
4. Poll search job status rather than assuming completion.
5. When adding new endpoints, update both this guide and the Postman collection.
6. Document any environment-specific config needed for testing.
