# Status: Verified Lead Bundle

- Gate 1 — Product: APPROVED 2026-11-16
- Gate 2 — Architecture: APPROVED 2026-11-16 (amended: tiered verifier, mx default)
- Gate 3 — Program Design: APPROVED 2026-11-16
- Gate 4 — Slice plan: APPROVED 2026-11-16

## Slices
- [x] Slice 1 — tracer bullet: migration + verification queue/worker stub + verify endpoint + enqueue switch
  - proof 2026-11-16: POST /businesses/{id}/verify -> 202; verification.log job_completed;
    contacts.verification_status=UNKNOWN (method=stub); scoring job followed;
    admin/queues shows verification complete=1
- [ ] Slice 2 — real MX email verification + phone line typing
- [ ] Slice 3 — bulk verify, force refresh, 30-day freshness skip
- [ ] Slice 4 — provenance writes in all stages + provenance API/response
- [ ] Slice 5 — verified/mobile lead filters + list UI badges
- [ ] Slice 6 — verified-only suppression-safe exports + export UI coverage
- [ ] Slice 7 — detail proof panel, admin queue, env/Makefile/README polish

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
