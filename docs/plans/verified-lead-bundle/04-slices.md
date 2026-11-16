# Slices: Verified Lead Bundle

Build order. Each slice ends in something runnable and demonstrable. No slice may
be "all backend" or "all UI" — every slice crosses at least two layers.

## Slice 1 — Tracer bullet: verify this lead, end to end

- Migration: contact verification columns, `field_provenance`, `suppressions`.
- `verification` queue name + `VerificationJobData`; new worker package with a
  stub processor that marks email contacts `UNKNOWN` and enqueues `scoring`.
- Contact and social workers enqueue `verification` instead of `scoring`.
- `POST /businesses/{id}/verify` returns 202 and enqueues the job.
- **Proof:** curl the endpoint on a real lead → queue runs → `contacts.verification_status`
  changes to `UNKNOWN` → `lead_scores` recalculates → `job_queue_logs` shows the
  verification job.

## Slice 2 — Real MX + phone verification

- `packages/verification_core`: MX lookup with per-domain cache, `MxEmailVerifier`
  (MX present → `RISKY`, missing → `INVALID`), `classify_phone` (mobile/landline/
  voip/toll-free/unknown), timeout handling.
- Worker writes status, confidence, reason, method, `verified_at`, `line_type`,
  and keeps `is_verified` in sync.
- **Proof:** re-run verification on Dental Square and a junk contact → valid
  domain gets `RISKY` + `MOBILE`, dead domain gets `INVALID`, worker never crashes
  on DNS failure.

## Slice 3 — Bulk, force, and freshness

- `POST /businesses/verify` (filters + 500 cap), `force` flag, 30-day reuse skip.
- Deterministic job id collapses contact+social duplicate enqueues.
- **Proof:** bulk verify a filtered segment → `queued` count matches; second call
  skips fresh rows; `force=true` re-checks and updates `last_checked`.

## Slice 4 — Provenance written everywhere + exposed

- `record_provenance` upsert helper; call it from discovery, website, contact,
  social, verification.
- `GET /businesses/{id}/provenance`; lead detail response includes `provenance`
  and `contacts[].verification`.
- **Proof:** lead detail JSON shows at least 4 fields with source + first seen +
  last checked; re-running a stage updates `last_checked` but not `first_seen`.

## Slice 5 — Verified filters in the lead list (API + UI)

- `GET /leads?verified_email=true&has_mobile=true`, counts, and summary numbers.
- Web: verification badges, confidence bar, verified/mobile toggles, hidden-count
  chips (matches mockup `leads-verified.html`).
- **Proof:** browser test — toggling "Verified email only" drops unverified rows
  and updates the counts.

## Slice 6 — Verified, suppression-safe exports

- `ExportFilters.verified_email_only` default true; suppression CRUD + enforcement;
  export columns (`email_status`, `email_verified_at`, `phone_type`).
- Web export modal coverage block + verified-only toggle; suppression always on.
- **Proof:** export twice (verified on/off) → row counts differ; add a suppressed
  email → it disappears from the next export; XLSX/CSV contain status columns.

## Slice 7 — Lead detail proof panel + polish

- Web: verification card, provenance table, re-verify button, catch-all warning,
  stale badge (matches `lead-detail.html`).
- Admin queue row for `verification`; logs/metrics; `.env.example`; README note;
  Makefile worker target.
- **Proof:** browser walkthrough of the detail page; admin queue shows verification
  jobs; restart workers from the documented commands.

## Definition of done for the feature

- All 30 Gate 3 tests exist and pass; ruff + mypy + full unit suite green.
- A fresh search job produces leads where ≥70% have a `VALID` or `RISKY` email
  status and ≥50% have a classified phone (threshold depends on configured
  verifier, per amended Gate 1 metric).
- A verified export excludes unverified and suppressed rows and includes
  verification columns.
- A new session can resume from `00-status.md` alone.
