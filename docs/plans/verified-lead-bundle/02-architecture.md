# Architecture: Verified Lead Bundle

## Fit

Touches four existing layers; no rewrite of the core pipeline.

- **Pipeline:** insert a `verification` stage between contact/social and scoring.
  Both `contact_processor` and `social_processor` currently enqueue `scoring`;
  they will enqueue `verification` instead. Verification enqueues `scoring` after
  it finishes (success or soft-fail), so scoring always runs.
- **New workspace package:** `packages/verification_core` (`leadforge_verification`)
  for email/phone verification logic. Keeps network-heavy verification out of
  `scraper_core` and out of the API, and follows the roadmap rule that new
  enrichment workers plug in without touching API core.
- **Database:** four additive changes (see Data). No destructive migration.
- **API:** new verification/provenance/suppression routes; extended lead, contact
  and export contracts.
- **Workers:** new `workers/verification_worker` (`leadforge_verification_worker`),
  same `WorkerWrapper`/`run_worker` pattern. Admin queue list, Makefile, queue
  name literal and `.env.example` gain `verification`.

## Endpoints

| Verb + route | Purpose |
|---|---|
| `POST /api/v1/businesses/{id}/verify` | Enqueue verification for one lead (user-scoped). 202 `{queued: true}` |
| `POST /api/v1/businesses/verify` | Bulk: accepts the same filters as `GET /leads`; enqueues up to 500 matching leads. 202 `{queued: N}` |
| `GET /api/v1/businesses/{id}/provenance` | Field provenance rows for the lead detail panel |
| `GET /api/v1/leads` | New query params: `verified_email=true`, `has_mobile=true` |
| `GET /api/v1/businesses/{id}` | Response gains `contacts[].verification` and `provenance[]` |
| `GET /api/v1/suppressions` | List the caller's suppression entries |
| `POST /api/v1/suppressions` | Add `{kind, value, reason?, note?}`; normalizes value |
| `DELETE /api/v1/suppressions/{id}` | Remove an entry |
| `POST /api/v1/exports` | `ExportFilters` gains `verified_email_only` (default `true`) |

All routes keep the existing envelope (`success/data/meta`) and tenant scoping via
`user_business_ids`.

## Data

### 1. `contacts` — add verification columns

```
verification_status   Enum(UNVERIFIED, VALID, RISKY, CATCH_ALL, INVALID, UNKNOWN)
                      default UNVERIFIED, not null
verification_confidence  Integer, default 0
verification_reason   Text, null            -- "mx_missing", "smtp_550", "provider_timeout"
verification_method   String(32), null      -- "smtp", "provider:zerobounce", "phone_lib"
verified_at           timestamptz, null
line_type             Enum(MOBILE, LANDLINE, VOIP, TOLL_FREE, UNKNOWN), null
                      -- phones only; NULL for email/social rows
```

`is_verified` stays for compatibility and is written as
`verification_status == VALID`. Queries that need precision use the enum.

Index: `(business_id, type, verification_status)` for the verified filter, plus
`(verified_at)` for the stale sweep.

### 2. `field_provenance` — new table

```
id, business_id FK, field String(64), value Text,
source String(32)            -- google_maps | website | social | directory | manual | verification
source_url Text, null
confidence Integer default 50,
first_seen_at timestamptz, last_checked_at timestamptz,
enrichment_run_id UUID null
UNIQUE (business_id, field, value)
INDEX (business_id, field)
```

Written by an upsert helper (`record_provenance`) from discovery, website, contact,
social and verification stages. `first_seen_at` never changes; `last_checked_at`
and `confidence` do.

Main query: `WHERE business_id = :id ORDER BY first_seen_at DESC` for the detail
panel; `UNIQUE` makes the write idempotent across re-runs.

### 3. `suppressions` — new table

```
id, user_id FK, kind Enum(EMAIL, PHONE, DOMAIN),
value Text (normalized: lowercase email, E.164 phone, lowercase domain),
reason String(64), note Text null, created_at
UNIQUE (user_id, kind, value)
```

Workspace-scoped to the user. Export and verification both consult it.

### 4. `exports` — no schema change

`filters` JSONB already stores the filter payload; the new key rides along.
`total_records` keeps meaning "rows written".

No new audit table: `contacts` holds the latest result, `field_provenance` holds
the history summary, and `enrichment_runs` records the worker run. Per-attempt
history is out of scope for v1 (noted in Gate 3 as a least-confident decision).

## Flow

Main path (single lead, post-enrichment):

1. `contact_processor` / `social_processor` write contacts, upsert provenance,
   `enqueue_job("verification", ...)` with `_job_id = "verify:{business_id}"`
   (collapses duplicate enqueues from the two stages).
2. `verification_worker.process`:
   - load business + contacts + `user` suppression list via the business's
     search-job owner (if a business belongs to multiple users, verify once;
     suppression only affects the export, not the shared record).
   - skip contacts with `verified_at` newer than 30 days unless `force`.
   - emails: syntax → MX (`dnspython`, cached per domain) → SMTP RCPT probe
     (no DATA) or provider adapter. Per-domain semaphore, 10 s timeout.
   - phones: `phonenumbers` parse + line type; no network call.
3. Write `contacts` verification columns, upsert provenance
   (`field=email_status` / `phone_type`), set `is_verified`.
4. Soft-fail anything that cannot be checked → `UNKNOWN` + reason; never raise.
5. `enqueue_job("scoring", ...)`.
6. `export_worker` applies `verified_email_only` + suppression before writing the
   file and adds verification columns.

Bulk verify: route resolves user-scoped business IDs, enqueues per lead, returns
count immediately. No long-running request.

## External

- **New dependency:** `dnspython>=2.6` for MX lookups (no other new libs;
  `phonenumbers` already exists).
- **Outbound SMTP (port 25):** measured **blocked on this host** (25 and 587 both
  time out), so SMTP cannot be the default. Verification is tiered:
  - `mx` (default): DNS + MX only → `RISKY`, confidence ~60. Works everywhere,
    proves the domain accepts mail, not that the mailbox exists.
  - `smtp`: adds RCPT probe → `VALID` / `INVALID`. Requires port 25.
  - `zerobounce` (or similar): provider result → `VALID` / `CATCH_ALL` /
    `INVALID`. Requires a key.
  Only `smtp` and provider results produce `VALID`; `verified_email_only`
  therefore depends on one of them being configured.
- **Optional provider:** ZeroBounce (first adapter) behind an interface.
- **Env var names only:**
  `EMAIL_VERIFIER_PROVIDER` (`mx` default, `smtp`, `zerobounce`),
  `ZEROBOUNCE_API_KEY`,
  `VERIFY_TIMEOUT_MS` (default 10000),
  `VERIFY_MAX_AGE_DAYS` (default 30),
  `VERIFY_SMTP_HELO_DOMAIN`,
  `VERIFY_MAX_CONCURRENCY` (default 5).
- No public inbound webhooks in v1.
