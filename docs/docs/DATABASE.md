# DATABASE.md

# LeadForge AI Database Design

Version: 1.0

Status: Approved

Database: PostgreSQL

ORM: SQLAlchemy 2.0 (async) + Alembic

---

# Database Philosophy

The database is the source of truth.

Workers may:

* Read
* Create
* Update

Workers must never:

* Delete business records
* Modify schema
* Run migrations

All schema changes must be performed through Alembic migrations.

---

# Design Principles

1. Normalize important data.
2. Avoid duplicated business records.
3. Store raw discovery data.
4. Store enriched data separately.
5. Preserve auditability.
6. Support future CRM integrations.
7. Support millions of businesses.

---

# Entity Relationship Overview

```text
SearchJob
    │
    ▼
Business
    │
    ├──────── Website
    │
    ├──────── Contacts
    │
    ├──────── SocialProfiles
    │
    ├──────── LeadScore
    │
    └──────── EnrichmentRuns
```

---

# TABLE: users

Purpose:

Authentication and ownership.

```sql
id UUID PK

email VARCHAR(255) UNIQUE

password_hash TEXT

full_name VARCHAR(255)

role VARCHAR(50)

is_active BOOLEAN

created_at TIMESTAMP

updated_at TIMESTAMP
```

Indexes:

```sql
email
```

---

# TABLE: search_jobs

Purpose:

Track searches initiated by users.

Example:

```text
Dentists in Houston
Restaurants in London
```

```sql
id UUID PK

user_id UUID FK

keyword VARCHAR(255)

location VARCHAR(255)

radius_km INTEGER

status VARCHAR(50)

total_discovered INTEGER

total_enriched INTEGER

started_at TIMESTAMP

completed_at TIMESTAMP

created_at TIMESTAMP
```

Status values:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

Indexes:

```sql
user_id
status
created_at
```

---

# TABLE: businesses

Purpose:

Master business record.

Every discovered business gets exactly one record.

```sql
id UUID PK

external_id VARCHAR(255)

name VARCHAR(500)

category VARCHAR(255)

address TEXT

city VARCHAR(255)

state VARCHAR(255)

country VARCHAR(255)

postal_code VARCHAR(50)

latitude DECIMAL(10,8)

longitude DECIMAL(11,8)

phone VARCHAR(100)

rating DECIMAL(3,2)

review_count INTEGER

source VARCHAR(50)

website_status VARCHAR(50)

is_claimed BOOLEAN

created_at TIMESTAMP

updated_at TIMESTAMP
```

website_status:

```text
UNKNOWN
FOUND
NOT_FOUND
INVALID
```

Indexes:

```sql
name
city
country
source
website_status
```

Unique Constraint:

```sql
external_id
```

---

# TABLE: search_job_businesses

Purpose:

Many-to-many relation.

One business may appear in many searches.

```sql
id UUID PK

search_job_id UUID FK

business_id UUID FK

created_at TIMESTAMP
```

Indexes:

```sql
search_job_id
business_id
```

---

# TABLE: websites

Purpose:

Store website information.

```sql
id UUID PK

business_id UUID FK UNIQUE

url TEXT

domain VARCHAR(255)

ssl_enabled BOOLEAN

is_reachable BOOLEAN

http_status INTEGER

load_time_ms INTEGER

mobile_friendly BOOLEAN

seo_score INTEGER

last_checked_at TIMESTAMP

created_at TIMESTAMP

updated_at TIMESTAMP
```

Indexes:

```sql
domain
business_id
```

---

# TABLE: contacts

Purpose:

Store all discovered contact methods.

```sql
id UUID PK

business_id UUID FK

type VARCHAR(50)

value TEXT

source VARCHAR(50)

confidence_score INTEGER

is_verified BOOLEAN

created_at TIMESTAMP
```

type values:

```text
EMAIL
PHONE
WHATSAPP
CONTACT_FORM
FACEBOOK
INSTAGRAM
LINKEDIN
YOUTUBE
TIKTOK
TWITTER
```

source values:

```text
MAPS
WEBSITE
SOCIAL
DIRECTORY
MANUAL
```

confidence_score:

```text
0-100
```

Indexes:

```sql
business_id
type
value
```

---

# TABLE: social_profiles

Purpose:

Store social accounts.

```sql
id UUID PK

business_id UUID FK

platform VARCHAR(50)

profile_url TEXT

username VARCHAR(255)

followers INTEGER

following INTEGER

posts_count INTEGER

bio TEXT

website TEXT

public_email TEXT

public_phone TEXT

last_activity_at TIMESTAMP

created_at TIMESTAMP

updated_at TIMESTAMP
```

platform:

```text
FACEBOOK
INSTAGRAM
LINKEDIN
YOUTUBE
TIKTOK
TWITTER
```

Indexes:

```sql
business_id
platform
username
```

Unique:

```sql
platform
profile_url
```

---

# TABLE: lead_scores

Purpose:

Lead qualification engine output.

One active score per business.

```sql
id UUID PK

business_id UUID FK UNIQUE

score INTEGER

grade VARCHAR(5)

best_contact_method VARCHAR(100)

website_opportunity_score INTEGER

social_activity_score INTEGER

contact_quality_score INTEGER

business_validation_score INTEGER

review_score INTEGER

notes TEXT

calculated_at TIMESTAMP

created_at TIMESTAMP
```

Grade Mapping:

```text
A+ = 95-100
A  = 90-94
B  = 80-89
C  = 60-79
D  = 40-59
F  = 0-39
```

Indexes:

```sql
score
grade
best_contact_method
```

---

# TABLE: enrichment_runs

Purpose:

Track every enrichment attempt.

Critical for debugging.

```sql
id UUID PK

business_id UUID FK

worker_name VARCHAR(100)

status VARCHAR(50)

started_at TIMESTAMP

completed_at TIMESTAMP

error_message TEXT

metadata JSONB

created_at TIMESTAMP
```

Status:

```text
PENDING
RUNNING
COMPLETED
FAILED
```

Indexes:

```sql
business_id
worker_name
status
```

---

# TABLE: exports

Purpose:

Track generated exports.

```sql
id UUID PK

user_id UUID FK

format VARCHAR(20)

file_path TEXT

total_records INTEGER

status VARCHAR(50)

created_at TIMESTAMP
```

format:

```text
CSV
XLSX
JSON
```

Indexes:

```sql
user_id
status
```

---

# TABLE: job_queue_logs

Purpose:

Worker observability.

```sql
id UUID PK

job_id VARCHAR(255)

queue_name VARCHAR(100)

worker_name VARCHAR(100)

status VARCHAR(50)

duration_ms INTEGER

error_message TEXT

created_at TIMESTAMP
```

Indexes:

```sql
queue_name
status
created_at
```

---

# Soft Deletes

Do NOT hard delete:

```text
Businesses
Contacts
Social Profiles
Lead Scores
```

Use:

```sql
deleted_at TIMESTAMP NULL
```

when deletion support is added.

---

# SQLAlchemy Conventions

Every table must include:

```sql
created_at
updated_at
```

SQLAlchemy mapping:

```python
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

# JSONB Usage Rules

Allowed only for:

```text
enrichment_runs.metadata
```

Do not store business data in JSON blobs.

Use relational columns.

---

# Database Performance Rules

Required Indexes:

* business name
* city
* country
* website status
* lead score
* contact type
* social platform

Queries must remain performant for:

```text
1,000,000+ businesses
10,000,000+ contacts
```

---

# Codex Database Rules

1. Use UUIDs everywhere.
2. Never use auto-increment IDs.
3. Use Alembic migrations only.
4. Use foreign keys.
5. Use indexes aggressively.
6. Normalize contact data.
7. Never store enrichment data in raw JSON.
8. Preserve audit history.
9. Prevent duplicate businesses.
10. Database is the source of truth.

