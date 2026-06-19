# LeadForge AI – Deployment Guide

Version: 2.0

Status: Production Ready Blueprint

---

# Purpose

This document defines how LeadForge AI is deployed, scaled, and operated in production.

It covers:

* Infrastructure setup
* Docker orchestration
* Environment configuration
* Scaling strategy
* Worker deployment
* Database setup
* Arq/Redis production usage

---

# Core Deployment Philosophy

LeadForge AI is designed as:

> A single API + multiple workers + shared database + queue-driven system

NOT:

* Microservices per feature
* Serverless functions per task
* Event-driven chaos architecture

---

# SYSTEM OVERVIEW

```text
FastAPI (Port 8000)
        ↓
PostgreSQL (5433)
        ↑
        ↓
Redis (6379) — Arq Queues
        ↓
Worker Fleet (6 worker types)
```

---

# INFRASTRUCTURE REQUIREMENTS

## Minimum Production Setup

```text
1x API Server (FastAPI + uvicorn)
1x PostgreSQL Server (15+)
1x Redis Server (7+)
1-3x Worker Nodes
```

## Recommended Setup (Scale)

```text
2x API Servers (uvicorn workers, load balanced)
1x PostgreSQL (Managed — RDS, Cloud SQL, etc.)
1x Redis Cluster (ElastiCache, Upstash, etc.)
3-10x Worker Nodes (auto-scaled by queue depth)
```

---

# DOCKER ARCHITECTURE

## Services

```text
api         — FastAPI (uvicorn)
postgres    — PostgreSQL 15
redis       — Redis 7
workers     — All 6 Arq workers (discovery, website, contact, social, scoring, export)
```

## Infrastructure Docker Compose

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: leadforge
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: leadforge
    ports:
      - "5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

---

# ENVIRONMENT VARIABLES

## API Environment

```text
DATABASE_URL=postgresql+asyncpg://user:pass@host:5433/leadforge
DATABASE_URL_SYNC=postgresql://user:pass@host:5433/leadforge
REDIS_HOST=localhost
REDIS_PORT=6379
JWT_SECRET=<strong-random-secret>
JWT_ALGORITHM=HS256
JWT_EXPIRES_HOURS=24
EXPORT_DIR=./exports
LOG_LEVEL=INFO
LOG_JSON=true
```

## Worker Environment

```text
DATABASE_URL=postgresql+asyncpg://user:pass@host:5433/leadforge
REDIS_HOST=localhost
REDIS_PORT=6379
SCRAPER_CONCURRENCY=3
SCRAPER_REQUEST_DELAY_MS=2000
SCRAPER_REQUEST_TIMEOUT_MS=10000
PLAYWRIGHT_HEADLESS=true
LOG_LEVEL=INFO
LOG_JSON=true
```

---

# DATABASE DEPLOYMENT

## PostgreSQL Requirements

* UUID extension enabled
* Indexing on: business name, city, country, website status, lead score, contact type, social platform

## Migration Strategy

Only the API service runs migrations:

```bash
uv run --package leadforge-database alembic upgrade head
```

Never run migrations from workers.

---

# REDIS / ARQ DEPLOYMENT

## Requirements

* Persistent Redis storage enabled (AOF)
* No in-memory queue usage
* Redis must not be flushed in production

## Queue Naming

Each worker consumes its own queue:

```text
arq:queue:discovery
arq:queue:website
arq:queue:contact
arq:queue:social
arq:queue:scoring
arq:queue:export
```

## Worker Scaling Model

Workers are horizontally scalable.

```text
discovery-worker x3
website-worker   x3
contact-worker   x3
social-worker    x2
scoring-worker   x2
export-worker    x1
```

Each instance pulls from the same Redis queue.

---

# DEPLOYMENT STRATEGY

## Phase 1: Local Development

```bash
docker compose -f infra/docker/docker-compose.yaml up -d postgres redis
uv run --package leadforge-database alembic upgrade head
uv run --package api uvicorn leadforge_api.main:app --reload --port 8000
uv run --package discovery-worker python -m leadforge_discovery_worker
```

## Phase 2: Single VPS Deployment

* Docker Compose with all services
* NGINX reverse proxy (optional)
* Systemd units for workers

## Phase 3: Production Scaling

* API behind load balancer
* Worker fleet scaled independently
* PostgreSQL managed service
* Redis cluster

---

# API DEPLOYMENT

## Start API

```bash
uv run --package api uvicorn leadforge_api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Health Check

```http
GET /health
```

Response:

```json
{
  "success": true,
  "service": "leadforge-api"
}
```

---

# WORKER DEPLOYMENT

## Worker Startup

Each worker runs independently:

```bash
uv run --package discovery-worker python -m leadforge_discovery_worker
uv run --package website-worker python -m leadforge_website_worker
uv run --package contact-worker python -m leadforge_contact_worker
uv run --package social-worker python -m leadforge_social_worker
uv run --package scoring-worker python -m leadforge_scoring_worker
uv run --package export-worker python -m leadforge_export_worker
```

## Crash Recovery

Workers must:

* Resume from last job (Arq handles job persistence)
* Retry failed jobs automatically (3 attempts, exponential backoff)
* Not lose state

---

# SCALING RULES

## API Scaling

* Stateless (no session storage)
* Horizontal scaling safe
* uvicorn workers = CPU count

## Worker Scaling

Scale based on queue depth:

```text
If queue > 1000 jobs → add workers
If queue < 100 jobs → reduce workers
```

## Redis Scaling

* Use Redis persistence (AOF enabled)
* Avoid memory-only mode
* Monitor memory usage

---

# PERFORMANCE CONFIGURATION

## Worker Concurrency

```text
SCRAPER_CONCURRENCY=3
```

Too high → scraping blocks / rate-limited

Too low → slow pipeline

## Rate Limiting

Required per worker:

* delay between requests (SCRAPER_REQUEST_DELAY_MS)
* circuit breakers per source
* retry backoff

---

# MONITORING

## Required Metrics

API:

* request latency
* error rate

Workers:

* jobs processed
* failure rate
* avg duration

Queue:

* backlog size (get_queue_stats)
* failed jobs count

## Logging

All logs must be:

* structured JSON (structlog)
* centralized
* searchable

---

# SECURITY DEPLOYMENT RULES

* No exposed Redis publicly
* PostgreSQL not publicly open
* API behind auth (JWT)
* Rate limiting enabled on API

---

# BACKUP STRATEGY

## PostgreSQL

* Daily backups
* Point-in-time recovery

## Redis

* Persistence enabled (AOF)
* Periodic snapshot

---

# FAILURE RECOVERY

If system crashes:

1. Redis restores queued jobs
2. Workers resume automatically
3. API remains stateless
4. No manual recovery needed

---

# DEPLOYMENT CHECKLIST

Before production:

* [ ] Database migrations run (alembic upgrade head)
* [ ] Redis persistence enabled
* [ ] Worker concurrency tested
* [ ] API health endpoint working
* [ ] Queue system tested
* [ ] Docker compose validated
* [ ] Logs verified
* [ ] JWT_SECRET changed from default
* [ ] EXPORT_DIR exists and writable

---

# FINAL RULE

If deployment requires manual intervention during normal operation:

> The architecture is wrong.

System must be self-recovering.
