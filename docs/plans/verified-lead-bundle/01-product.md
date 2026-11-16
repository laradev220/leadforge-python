# Product: Verified Lead Bundle

## Problem

In the user's words:

> "I export a few hundred local businesses, and I still don't know which emails
> will bounce, which phone numbers are even mobile, or where a field came from.
> Apollo gives me people at big companies — not the dentist, clinic, or restaurant
> I actually sell websites to. So I spend my first hour cleaning the list, my
> second hour guessing, and my domain reputation pays for it."

Three concrete pains:

1. **Unverified contact data.** Emails are scraped from pages with no proof they
   accept mail; phone numbers are not typed (mobile vs switchboard); socials are
   missing or stale.
2. **No provenance.** Users cannot see which source produced a value, when it was
   last checked, or why they should trust it.
3. **No verified handoff.** Exports are unfiltered dumps. There is no way to say
   "give me only leads whose email passed verification, and exclude anyone who
   asked not to be contacted."

Apollo solves the first pain for large B2B companies at credit-based pricing and
with a 60–73% accuracy ceiling outside North America. It does not solve local SMB
depth or per-field transparency, and its credit model makes list cleaning
expensive.

## Success metric

**Primary:** ≥70% of exported leads carry a verified email, and the verified set
sustains a hard-bounce rate <3% over the first 30 days after export.

**Measured by:** verification status recorded at export time + bounce feedback
from CRM/CSV re-import (manual in v1, webhook in a later feature). Secondary
instrumentation: % of leads with a verified phone type, % of fields with
provenance, median verification age.

## Announcement — the blog post before the feature

> **Every lead now ships with proof.**
>
> LeadForge no longer hands you a raw list and wishes you luck. Each email is
> checked against the domain and mailbox before it reaches your export, every
> phone number is typed, and every field shows where it came from and when it was
> last verified. Flip on "Verified only" and your export contains exactly the
> leads we would contact ourselves — with suppressed and do-not-contact records
> removed. No credits, no mystery scores, no cleaning spreadsheet. This is the
> local-business list Apollo never built.

## Screens

- `mockups/lead-detail.html` — per-lead verification panel: email/phone/social
  badges, confidence, provenance table (source, first seen, last checked), and a
  re-verify action.
- `mockups/leads-verified.html` — lead list with a "Verified email only" toggle,
  verification/confidence columns, and visible source chips.
- `mockups/export-verified.html` — export builder that enforces verified-only +
  suppression, shows the resulting count/coverage before download, and offers
  CRM/Sheets delivery.

## Scope for this feature (v1)

In:
- Email verification for business emails found by the pipeline
  (syntax → domain/MX → SMTP/provider result) with a stored status, reason,
  confidence, and checked-at.
- Phone classification (mobile / landline / invalid) using an offline library,
  no live calls in v1.
- Per-field provenance: source, first seen, last checked, enrichment run id.
- Verified-only filter on leads list and exports; suppression list enforced.
- Lead detail + list + export UI as mocked.
- Re-verify action per lead and bulk for a filtered set.

Out (later features):
- Person-level contacts (Apollo's core), waterfall across paid vendors.
- Outreach sequencing, dialer, inbox warmup.
- Scheduled/recurring runs, CRM two-way sync, team assignment.
- Bounce-credit guarantee and automated bounce ingestion.

## Why this makes us stand out (market context)

Apollo's background: a 2M+ contributor network (connected inboxes/CRMs), public
web crawling, vetted third-party vendors, a governed waterfall across 20+ vendors,
and a 7-step verifier that uses mailbox/CRM traffic signals to beat SMTP-only
tools on catch-all domains. Strengths we will not beat: 230M+ contacts, sequencing,
dialer, 200+ integrations. Weaknesses we can beat for our buyer: local SMB depth,
international accuracy, credit opacity, and no per-field provenance.

Our wedge: **local businesses + proof + no credits**. Every claim is inspectable;
verification is included rather than metered; the export is safe by default.
