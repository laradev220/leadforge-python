# LeadForge AI API Specification

> **Version:** 1.0
> **Base URL:** `/api/v1`
> **Content Type:** `application/json`
> **Auth:** JWT Bearer Token

---

## Table of Contents

- [API Philosophy](#api-philosophy)
- [Response Format](#response-format)
- [Error Codes](#error-codes)
- [Authentication](#authentication)
- [Pagination](#pagination)
- [Auth Module](#-auth-module)
- [Search Jobs Module](#-search-jobs-module)
- [Businesses Module](#-businesses-module)
- [Leads Module](#-leads-module)
- [Analytics Module](#-analytics-module)
- [Exports Module](#-exports-module)
- [Social Profiles Module](#-social-profiles-module)
- [Scrapers Module](#-scrapers-module)
- [Admin Module](#-admin-module)
- [System Endpoints](#-system-endpoints)
- [Data Models](#data-models)
- [HTTP Status Codes](#http-status-codes)

---

## API Philosophy

The API is responsible for:

- Authentication & user management
- Search job creation and management
- Business and lead retrieval
- Export generation
- Dashboard analytics
- Scraper health monitoring

The API is **NOT** responsible for:

- Scraping websites or directories
- Crawling business data
- Enrichment or website analysis
- Contact extraction

All long-running work is delegated to **Arq workers** via Redis queues.

---

## Response Format

### Success (Single Object)

```json
{
  "success": true,
  "data": { ... }
}
```

### Success (List with Pagination)

```json
{
  "success": true,
  "data": [ ... ],
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 100,
    "totalPages": 2
  }
}
```

### Error

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request",
    "context": {
      "errors": [
        {
          "type": "string_too_short",
          "loc": ["body", "keyword"],
          "msg": "String should have at least 1 character",
          "input": ""
        }
      ]
    }
  }
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|---|---|---|
| `BAD_REQUEST` | 400 | Invalid request parameters |
| `UNAUTHORIZED` | 401 | Missing or invalid token |
| `TOKEN_EXPIRED` | 401 | JWT has expired |
| `FORBIDDEN` | 403 | Insufficient permissions (e.g., not admin) |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource conflict (e.g., duplicate email) |
| `VALIDATION_ERROR` | 422 | Request body/params validation failed |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## Authentication

### Headers

```
Authorization: Bearer <jwt-token>
```

### Auth Flow

1. `POST /api/v1/auth/register` — Create account, receive JWT
2. `POST /api/v1/auth/login` — Login, receive JWT
3. Include `Authorization: Bearer <token>` in subsequent requests
4. `GET /api/v1/auth/me` — Verify token and get current user

### Token Claims

```json
{
  "sub": "uuid",
  "id": "uuid",
  "email": "user@example.com",
  "iat": 1700000000,
  "exp": 1700086400
}
```

### Token Expiry

Default: **24 hours** (configurable via `JWT_EXPIRES_HOURS`)

---

## Pagination

### Request

| Parameter | Type | Default | Max | Description |
|---|---|---|---|---|
| `page` | integer | 1 | - | Page number (1-indexed) |
| `limit` | integer | 50 | 100 | Items per page |

### Response

```json
{
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 1000,
    "totalPages": 20
  }
}
```

---

## 🔐 Auth Module

### POST Register

Create a new user account.

```
POST /api/v1/auth/register
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secret123",
  "fullName": "John Doe"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✅ | Valid email address |
| `password` | string | ✅ | Min 8 characters |
| `fullName` | string | ❌ | User's display name |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "USER",
      "created_at": "2026-01-01T00:00:00Z"
    },
    "token": "eyJhbGciOiJIUzI1NiIs..."
  }
}
```

### POST Login

Authenticate and receive a JWT token.

```
POST /api/v1/auth/login
```

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secret123"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✅ | Registered email |
| `password` | string | ✅ | Account password |

**Response (200):**
```json
{
  "success": true,
  "data": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "user": {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "full_name": "John Doe",
      "role": "USER",
      "created_at": "2026-01-01T00:00:00Z"
    }
  }
}
```

### GET Me

Get the currently authenticated user's profile.

```
GET /api/v1/auth/me
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "full_name": "John Doe",
    "role": "USER",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

---

## 🔍 Search Jobs Module

Search jobs are the entry point for lead discovery. Creating one enqueues a discovery worker job that scrapes Google Maps and directories for matching businesses.

### POST Create Search Job

```
POST /api/v1/search-jobs
```

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "keyword": "Dentist",
  "location": "Houston",
  "radius_km": 25,
  "country": "US"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `keyword` | string | ✅ | What to search for (e.g., "Restaurant", "Plumber") |
| `location` | string | ✅ | Location to search in (e.g., "London", "New York") |
| `radius_km` | integer | ❌ | Search radius in kilometers |
| `country` | string | ❌ | ISO-3166-1 alpha-2 country code (e.g., US, GB, PK) |

**Behavior:**
1. Creates a `SearchJob` record with `PENDING` status
2. Enqueues a discovery job on the `discovery` Arq queue
3. Returns the job ID immediately

**Response (200):**
```json
{
  "success": true,
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "PENDING"
  }
}
```

### GET List Search Jobs

```
GET /api/v1/search-jobs?page=1&limit=50&status=PENDING
```

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | integer | 1 | Page number |
| `limit` | integer | 50 | Items per page (max 100) |
| `status` | string | - | Filter by status: `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "keyword": "Dentist",
      "location": "Houston",
      "radius_km": 25,
      "status": "COMPLETED",
      "total_discovered": 42,
      "total_enriched": 38,
      "started_at": "2026-01-01T00:00:00Z",
      "completed_at": "2026-01-01T01:00:00Z",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "limit": 50,
    "total": 1,
    "totalPages": 1
  }
}
```

### GET Search Job by ID

```
GET /api/v1/search-jobs/:id
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "user_id": "550e8400-e29b-41d4-a716-446655440001",
    "keyword": "Dentist",
    "location": "Houston",
    "radius_km": 25,
    "status": "COMPLETED",
    "total_discovered": 42,
    "total_enriched": 38,
    "started_at": "2026-01-01T00:00:00Z",
    "completed_at": "2026-01-01T01:00:00Z",
    "created_at": "2026-01-01T00:00:00Z"
  }
}
```

### POST Cancel Search Job

```
POST /api/v1/search-jobs/:id/cancel
```

**Headers:** `Authorization: Bearer <token>`

**Behavior:** Marks the job as `CANCELLED` to prevent downstream processing.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "cancelled": true
  }
}
```

---

## 🏢 Businesses Module

Businesses are discovered by search jobs and enriched by worker pipelines.

### GET List Businesses

```
GET /api/v1/businesses?page=1&limit=50&country=US&category=Restaurant&website_status=FOUND
```

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Items per page (default: 50, max: 100) |
| `name` | string | Filter by name (partial match, case-insensitive) |
| `city` | string | Filter by city (partial match) |
| `country` | string | Filter by country (exact match) |
| `category` | string | Filter by category (partial match) |
| `website_status` | string | Filter by website status: `UNKNOWN`, `FOUND`, `NOT_FOUND`, `INVALID` |
| `min_rating` | float | Minimum rating filter |
| `max_rating` | float | Maximum rating filter |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "external_id": "google_maps:abc123",
      "name": "Joe's Pizza",
      "category": "Restaurant",
      "address": "123 Main St",
      "city": "Houston",
      "state": "TX",
      "country": "US",
      "postal_code": "77001",
      "latitude": 29.7604,
      "longitude": -95.3698,
      "phone": "+1-555-0123",
      "rating": 4.5,
      "review_count": 128,
      "source": "GOOGLE_MAPS",
      "website_status": "FOUND",
      "is_claimed": true,
      "created_at": "2026-01-01T00:00:00Z",
      "updated_at": "2026-01-01T01:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 50, "total": 1, "totalPages": 1 }
}
```

### GET Business by ID

```
GET /api/v1/businesses/:id
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "external_id": "google_maps:abc123",
    "name": "Joe's Pizza",
    "category": "Restaurant",
    "address": "123 Main St",
    "city": "Houston",
    "state": "TX",
    "country": "US",
    "postal_code": "77001",
    "latitude": 29.7604,
    "longitude": -95.3698,
    "phone": "+1-555-0123",
    "rating": 4.5,
    "review_count": 128,
    "source": "GOOGLE_MAPS",
    "website_status": "FOUND",
    "is_claimed": true,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T01:00:00Z"
  }
}
```

### POST Re-Enrich Business

Triggers re-enrichment of a business (enqueues website, contact, and social workers).

```
POST /api/v1/businesses/:id/re-enrich
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "reEnriched": true
  }
}
```

### GET Business Website

```
GET /api/v1/businesses/:id/website
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "business_id": "550e8400-e29b-41d4-a716-446655440001",
    "url": "https://joespizza.example.com",
    "domain": "joespizza.example.com",
    "ssl_enabled": true,
    "is_reachable": true,
    "http_status": 200,
    "load_time_ms": 450,
    "mobile_friendly": true,
    "seo_score": 75,
    "last_checked_at": "2026-01-01T01:00:00Z"
  }
}
```

### GET Business Contacts

```
GET /api/v1/businesses/:id/contacts
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "business_id": "550e8400-e29b-41d4-a716-446655440001",
      "type": "EMAIL",
      "value": "info@joespizza.com",
      "source": "WEBSITE",
      "confidence_score": 90,
      "is_verified": false,
      "created_at": "2026-01-01T01:00:00Z"
    }
  ]
}
```

**Contact Types:** `EMAIL`, `PHONE`, `WHATSAPP`, `CONTACT_FORM`, `FACEBOOK`, `INSTAGRAM`, `LINKEDIN`, `YOUTUBE`, `TIKTOK`, `TWITTER`

**Contact Sources:** `MAPS`, `WEBSITE`, `SOCIAL`, `DIRECTORY`, `MANUAL`

### POST Add Contact

Add a manual contact to a business.

```
POST /api/v1/businesses/:id/contacts
```

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "type": "EMAIL",
  "value": "hello@example.com"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "business_id": "550e8400-e29b-41d4-a716-446655440001",
    "type": "EMAIL",
    "value": "hello@example.com",
    "source": "MANUAL",
    "confidence_score": 50,
    "is_verified": false,
    "created_at": "2026-01-01T01:00:00Z"
  }
}
```

### GET Business Social Profiles

```
GET /api/v1/businesses/:id/social-profiles
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "business_id": "550e8400-e29b-41d4-a716-446655440001",
      "platform": "INSTAGRAM",
      "profile_url": "https://instagram.com/joespizza",
      "username": "joespizza",
      "followers": 1500,
      "following": 200,
      "posts_count": 340,
      "bio": "Best pizza in Houston!",
      "website": "https://joespizza.example.com",
      "public_email": null,
      "public_phone": null,
      "last_activity_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

**Platforms:** `FACEBOOK`, `INSTAGRAM`, `LINKEDIN`, `YOUTUBE`, `TIKTOK`, `TWITTER`

---

## ⭐ Leads Module

Leads are businesses that have been enriched and scored. They represent qualified opportunities for outreach.

### GET List Leads

```
GET /api/v1/leads?page=1&limit=50&score_min=80&grade=A&country=US
```

**Headers:** `Authorization: Bearer <token>`

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `limit` | integer | Items per page (default: 50, max: 100) |
| `score_min` | integer | Minimum lead score (filter) |
| `score_max` | integer | Maximum lead score (filter) |
| `grade` | string | Filter by grade: `A+`, `A`, `B`, `C`, `D`, `F` |
| `website_status` | string | Filter by website status |
| `best_contact_method` | string | Filter by best contact method |
| `city` | string | Filter by city |
| `country` | string | Filter by country |

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "business": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "name": "Joe's Pizza",
        "category": "Restaurant",
        "city": "Houston",
        "country": "US",
        "phone": "+1-555-0123",
        "rating": 4.5,
        "review_count": 128,
        "website_status": "FOUND"
      },
      "lead_score": {
        "id": "550e8400-e29b-41d4-a716-446655440001",
        "business_id": "550e8400-e29b-41d4-a716-446655440000",
        "score": 85,
        "grade": "A",
        "best_contact_method": "EMAIL",
        "website_opportunity_score": 80,
        "social_activity_score": 70,
        "contact_quality_score": 90,
        "review_score": 85,
        "business_validation_score": 95,
        "notes": "Strong online presence, verified contact",
        "calculated_at": "2026-01-01T01:00:00Z"
      },
      "contacts": [
        {
          "type": "EMAIL",
          "value": "info@joespizza.com",
          "confidence_score": 90
        }
      ],
      "social_profiles": [
        {
          "platform": "INSTAGRAM",
          "profile_url": "https://instagram.com/joespizza",
          "followers": 1500
        }
      ],
      "website": {
        "url": "https://joespizza.example.com",
        "domain": "joespizza.example.com",
        "ssl_enabled": true,
        "seo_score": 75
      }
    }
  ],
  "meta": { "page": 1, "limit": 50, "total": 1, "totalPages": 1 }
}
```

### GET Lead by ID

```
GET /api/v1/leads/:businessId
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):** Same structure as list item above.

---

## 📊 Analytics Module

### GET Dashboard Stats

```
GET /api/v1/analytics/dashboard
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "businesses": 1250,
    "websitesFound": 980,
    "emailsFound": 720,
    "socialProfilesFound": 540,
    "highValueLeads": 310
  }
}
```

### GET Lead Distribution

```
GET /api/v1/analytics/lead-distribution
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "distribution": {
      "A+": 50,
      "A": 120,
      "B": 300,
      "C": 200,
      "D": 80,
      "F": 30
    }
  }
}
```

---

## 📤 Exports Module

### POST Create Export

Creates an export job. The export worker asynchronously generates the file.

```
POST /api/v1/exports
```

**Headers:** `Authorization: Bearer <token>`

**Request Body:**
```json
{
  "format": "CSV",
  "filters": {
    "score_min": 60,
    "grade": "A",
    "country": "US",
    "city": "Houston",
    "website_status": "FOUND"
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `format` | string | ✅ | Export format: `CSV`, `JSON`, or `XLSX` |
| `filters` | object | ❌ | Filters to apply (see supported fields below) |

**Supported Filter Fields:**
- `score_min` — minimum lead score
- `score_max` — maximum lead score
- `grade` — lead grade (`A+`, `A`, `B`, `C`, `D`, `F`)
- `website_status` — website status
- `best_contact_method` — best contact method
- `city` — city filter
- `country` — country filter

**Response (201):**
```json
{
  "success": true,
  "data": {
    "export_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### GET List Exports

```
GET /api/v1/exports
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": "550e8400-e29b-41d4-a716-446655440001",
      "format": "CSV",
      "file_path": "exports/export-uuid.csv",
      "total_records": 500,
      "status": "COMPLETED",
      "created_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

### GET Download Export

Downloads the generated export file.

```
GET /api/v1/exports/:id/download
```

**Headers:** `Authorization: Bearer <token>`

**Response:**
- **200** — File stream with appropriate `Content-Type` header
- **404** — Not ready yet or file missing

**Error (404 - Not Ready):**
```json
{
  "success": false,
  "error": { "code": "NOT_READY", "message": "Export not ready" }
}
```

**Content Types by Format:**
| Format | Content-Type |
|---|---|
| CSV | `text/csv` |
| JSON | `application/json` |
| XLSX | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` |

---

## 👤 Social Profiles Module

### GET Social Profile by ID

```
GET /api/v1/social-profiles/:id
```

**Headers:** `Authorization: Bearer <token>`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "business_id": "550e8400-e29b-41d4-a716-446655440001",
    "platform": "INSTAGRAM",
    "profile_url": "https://instagram.com/joespizza",
    "username": "joespizza",
    "followers": 1500,
    "following": 200,
    "posts_count": 340,
    "bio": "Best pizza in Houston!",
    "website": "https://joespizza.example.com",
    "public_email": null,
    "public_phone": null,
    "last_activity_at": "2026-01-01T00:00:00Z"
  }
}
```

---

## 🔬 Scrapers Module

### GET Scraper Health (Public)

```
GET /api/v1/scrapers/health
```

No auth required.

**Response (200):**
```json
{
  "success": true,
  "service": "leadforge-scrapers",
  "timestamp": 1700000000.123,
  "sources": {
    "google_maps": {
      "status": "healthy",
      "failure_rate": 0.02,
      "last_scrape_at": "2026-01-01T00:00:00Z",
      "circuit_breaker": "closed"
    }
  }
}
```

### GET Scraper Metrics (Public)

```
GET /api/v1/scrapers/metrics
```

No auth required. Returns Prometheus-format metrics.

### GET Cache Stats (Admin)

```
GET /api/v1/scrapers/cache/stats
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Response (200):**
```json
{
  "success": true,
  "cache": {
    "keys": 1500,
    "estimated_size_bytes": 52428800
  }
}
```

### POST Cache Invalidate (Admin)

```
POST /api/v1/scrapers/cache/invalidate?url=https://example.com/page&user_agent=default
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Query Parameters:**
- `url` (required) — The cached URL to invalidate
- `user_agent` (default: "default") — The user agent used for caching

**Response (200):**
```json
{
  "success": true,
  "invalidated": true
}
```

### POST Cache Clear (Admin)

```
POST /api/v1/scrapers/cache/clear
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Response (200):**
```json
{
  "success": true,
  "keys_deleted": 1500
}
```

### GET Selector Stats (Admin)

```
GET /api/v1/scrapers/selectors/:source
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Response (200):**
```json
{
  "success": true,
  "source": "google_maps",
  "note": "Selector stats available via SelectorTracker.get_best_selector()"
}
```

---

## 🔧 Admin Module

### GET Queue Stats

```
GET /api/v1/admin/queues
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "stats": {
      "discovery": { "waiting": 5, "in_progress": 2, "complete": 100, "failed": 3 },
      "website": { "waiting": 3, "in_progress": 1, "complete": 80, "failed": 1 },
      "contact": { "waiting": 2, "in_progress": 1, "complete": 60, "failed": 0 },
      "social": { "waiting": 1, "in_progress": 0, "complete": 40, "failed": 0 },
      "scoring": { "waiting": 0, "in_progress": 1, "complete": 35, "failed": 0 },
      "export": { "waiting": 0, "in_progress": 0, "complete": 10, "failed": 0 }
    }
  }
}
```

### POST Retry Failed Jobs

Moves all failed jobs back to their respective waiting queues.

```
POST /api/v1/admin/queues/retry
```

**Headers:** `Authorization: Bearer <token>` (requires `ADMIN` role)

**Response (200):**
```json
{
  "success": true,
  "data": {
    "retried": 4
  }
}
```

---

## 🩺 System Endpoints

### GET /health

```
GET /health
```

No auth required. Returns basic API health status.

**Response (200):**
```json
{
  "success": true,
  "service": "leadforge-api"
}
```

### GET /health/scrapers

```
GET /health/scrapers
```

No auth required. Returns scraper subsystem health.

**Response (200):**
```json
{
  "success": true,
  "service": "leadforge-scrapers",
  "sources": { ... }
}
```

### GET /metrics

```
GET /metrics
```

No auth required. Returns Prometheus-format metrics.

---

## Data Models

### User

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique identifier |
| `email` | string | Email address (unique) |
| `full_name` | string or null | Display name |
| `role` | enum | `USER` or `ADMIN` |
| `is_active` | boolean | Whether the user is active |
| `created_at` | datetime (ISO 8601) | Creation timestamp |
| `updated_at` | datetime (ISO 8601) | Last update timestamp |

### SearchJob

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique identifier |
| `user_id` | UUID | Owner |
| `keyword` | string | Search keyword |
| `location` | string | Search location |
| `radius_km` | integer or null | Search radius |
| `status` | enum | `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`, `CANCELLED` |
| `total_discovered` | integer | Number of businesses discovered |
| `total_enriched` | integer | Number of businesses enriched |
| `started_at` | datetime or null | When processing started |
| `completed_at` | datetime or null | When processing completed |
| `created_at` | datetime | Creation timestamp |

### Business

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique identifier |
| `external_id` | string or null | External source ID |
| `name` | string | Business name |
| `category` | string or null | Business category |
| `address` | string or null | Full address |
| `city` | string or null | City |
| `state` | string or null | State/region |
| `country` | string or null | Country |
| `postal_code` | string or null | Postal/ZIP code |
| `latitude` | float or null | Latitude |
| `longitude` | float or null | Longitude |
| `phone` | string or null | Phone number |
| `rating` | float or null | Average rating |
| `review_count` | integer or null | Number of reviews |
| `source` | string | Data source (`GOOGLE_MAPS`, `DIRECTORY`, `MANUAL`) |
| `website_status` | enum | `UNKNOWN`, `FOUND`, `NOT_FOUND`, `INVALID` |
| `is_claimed` | boolean or null | Whether the business is claimed |
| `created_at` | datetime | Creation timestamp |
| `updated_at` | datetime | Last update timestamp |

### LeadScore

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique identifier |
| `business_id` | UUID | Associated business |
| `score` | integer | Overall score (0-100) |
| `grade` | string or null | Letter grade (`A+`, `A`, `B`, `C`, `D`, `F`) |
| `best_contact_method` | string or null | Best way to contact |
| `website_opportunity_score` | integer | Website quality sub-score |
| `social_activity_score` | integer | Social presence sub-score |
| `contact_quality_score` | integer | Contact quality sub-score |
| `review_score` | integer | Review analysis sub-score |
| `business_validation_score` | integer | Business validity sub-score |
| `notes` | string or null | Scoring notes |
| `calculated_at` | datetime | When score was calculated |

### Export

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Unique identifier |
| `user_id` | UUID | Owner |
| `format` | enum | `CSV`, `JSON`, `XLSX` |
| `file_path` | string or null | Path to generated file |
| `filters` | object or null | Export filters applied |
| `total_records` | integer | Number of records exported |
| `status` | string | `PENDING`, `COMPLETED`, `FAILED` |
| `created_at` | datetime | Creation timestamp |

---

## HTTP Status Codes

| Code | Name | Usage |
|---|---|---|
| `200` | OK | Successful GET, POST, PUT |
| `201` | Created | Resource created successfully |
| `400` | Bad Request | Invalid request parameters |
| `401` | Unauthorized | Missing or invalid JWT |
| `403` | Forbidden | Insufficient permissions (not admin) |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Duplicate or conflicting resource |
| `422` | Unprocessable Entity | Validation error in request body/params |
| `500` | Internal Server Error | Unexpected server error |

---

## Codex API Rules

1. **Controllers must remain thin** — Routes should only parse input and return responses
2. **Business logic belongs in services** — No heavy logic in route handlers
3. **Validation belongs in schemas** — Use Pydantic for request/response validation
4. **Never perform scraping inside API routes** — All scraping goes through workers
5. **Every long-running action must create a queue job** — No synchronous heavy processing
6. **Use DTOs for all requests** — Every request body should have a Pydantic schema
7. **Use consistent response format** — Always use `success` + `data`/`error` envelope
8. **Version all endpoints under `/api/v1`** — All routes mounted under the prefix
9. **API must remain stateless** — All state is in PostgreSQL or Redis
10. **JWT authentication required for all protected routes** — No unprotected sensitive endpoints
