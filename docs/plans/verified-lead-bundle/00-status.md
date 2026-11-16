# Status: Verified Lead Bundle

- Gate 1 — Product: APPROVED 2026-11-16
- Gate 2 — Architecture: APPROVED 2026-11-16 (amended: tiered verifier, mx default)
- Gate 3 — Program Design: APPROVED 2026-11-16
- Gate 4 — Slice plan: APPROVED 2026-11-16 — FEATURE COMPLETE 2026-11-16

## Slices
- [x] Slice 1 — tracer bullet: migration + verification queue/worker stub + verify endpoint + enqueue switch
  - proof 2026-11-16: POST /businesses/{id}/verify -> 202; verification.log job_completed;
    contacts.verification_status=UNKNOWN (method=stub); scoring job followed;
    admin/queues shows verification complete=1
- [x] Slice 2 — real MX email verification + phone line typing
  - proof 2026-11-16: info@signaturesmile.com.pk -> RISKY (mx_present, 60);
    contact@dentalsquarefamily.com -> INVALID (mx_missing, domain genuinely has no MX);
    +923139252147 -> VALID/MOBILE (phone_lib, 80); scoring followed each run
- [x] Slice 3 — bulk verify, force refresh, 30-day freshness skip
  - proof 2026-11-16: POST /businesses/verify {city:Peshawar,limit:3} -> queued=3, 3 jobs ran;
    repeat on fresh lead -> skipped_fresh=2, 0 network checks;
    ?force=true -> skipped_fresh=0, emails=1 phones=1; job id bucketed per minute
- [x] Slice 4 — provenance writes in all stages + provenance API/response
  - proof 2026-11-16: Signature Smile re-enrich -> 17 provenance rows (website,
    contact, social, verification); GET /leads/{id} includes provenance and
    contacts[].verification; repeat upsert keeps first_seen, refreshes last_checked
- [x] Slice 5 — verified/mobile lead filters + list UI badges
  - proof 2026-11-16: /leads?include_stats=true -> total 43, verified 0,
    domain-checked 1, mobile 5; has_mobile filter returns 5 leads with MOBILE;
    web typecheck clean (verification + phone badges, toggles, counts)
- [x] Slice 6 — verified-only suppression-safe exports + export UI coverage
  - proof 2026-11-16: suppressed info@signaturesmile.com.pk -> export with
    verified_email_only=false gave 42/43 rows (suppressed absent); default
    verified-only gave 0 (no mailbox-verified emails under mx tier);
    CSV headers include email_status, email_verified_at, phone_type
- [x] Slice 7 — detail proof panel, admin queue, env/Makefile/README polish
  - proof 2026-11-16: lead detail shows re-verify + verification badges + 17-row
    provenance table; admin queue labels include verification; README documents
    provider/env/commands; web typecheck clean; workers + API + web running
- Follow-up completed: SMTP + ZeroBounce adapters and provider selection
  (EMAIL_VERIFIER_PROVIDER); SMTP on this host -> RISKY smtp_unreachable (port 25 blocked)
- Known limits: verified filter/export is strict VALID (needs SMTP/provider);
  suppression has API only (no page); no per-attempt verification history

## Notes for a fresh session
- Program: make LeadForge standout for **local-business outbound** (agencies and
  software companies selling web/digital services), not a general B2B people DB.
- Differentiation thesis: Apollo wins on people coverage and sequencing; it is
  weak on local SMB depth, non-US accuracy, credit opacity, and per-field
  provenance. We win with **verified local business contacts + visible proof +
  no credit roulette**.
- Feature #1 (this plan): Verified Lead Bundle — verification status, confidence,
  provenance, verified-only filters, suppression-safe verified exports.
- Product docs live in `docs/docs/` (PRD, ROADMAP, LEAD_SCORING, OUTREACH_WORKFLOW).
  This plan folder is the Software Factory working set.
- Approval protocol: explicit "approve Gate N" required before advancing.
- Buyer assumption approved: agencies / software shops selling web and digital
  services to local businesses.
- Gate 2 decisions: new `verification` queue+worker; new
  `packages/verification_core`; additive migration (contacts columns,
  field_provenance, suppressions); export filter `verified_email_only` default
  true; SMTP verifier with optional ZeroBounce adapter; 30-day reuse.
