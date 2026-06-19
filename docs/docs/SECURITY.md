# SECURITY.md

# LeadForge AI – Security & Compliance Guidelines

Version: 1.0

Status: Critical

---

# Purpose

This document defines security rules, compliance boundaries, and safe operating constraints for all components of LeadForge AI.

This system interacts with:

* Public websites
* Search engines
* Business directories
* Social platforms
* Contact forms

Therefore it MUST operate safely, respectfully, and within acceptable usage patterns.

---

# Core Security Principle

> Just because data is public does NOT mean it can be aggressively harvested.

LeadForge AI must behave like:

* A low-frequency, human-like data collector
* NOT a bot farm
* NOT a brute-force scraper

---

# DATA USAGE POLICY

## Allowed Data Sources

System is allowed to process:

* Google Maps public listings
* Public business websites
* Public social media profiles
* Public directories
* Public contact pages

---

## Forbidden Data Sources

System MUST NOT access:

* Private accounts
* Login-protected pages
* Paywalled content
* CAPTCHA-protected flows (bypass forbidden)
* Hidden APIs without authorization
* Scraping behind authentication walls

---

# SCRAPING ETHICS RULES

## 1. Human-Like Behavior Required

All scraping MUST simulate:

* realistic delays
* randomized intervals
* limited concurrency
* natural browsing patterns

---

## 2. No Aggressive Crawling

Forbidden behaviors:

* mass parallel requests to same domain
* infinite crawling loops
* deep recursive crawling beyond limits
* repeated retries without backoff

---

## 3. Respect Robots Rules (Soft Compliance Model)

Even if robots.txt is not strictly enforced technically:

System MUST:

* avoid disallowed endpoints where detectable
* reduce load on servers
* avoid scraping sensitive endpoints

---

# RATE LIMITING POLICY

## Global Limits

```text id="r1p8qa"
Max Requests Per Domain: 1 request / 2–5 seconds
Max Parallel Sessions: 5
Max Retries: 3
```

---

## Exponential Backoff

Retry schedule:

```text id="b2k9qp"
1s → 3s → 10s → stop
```

---

# IP RISK MITIGATION

System MUST:

* rotate user agents
* avoid repetitive request patterns
* avoid high-frequency bursts
* distribute scraping across workers

Optional:

* proxy support (residential preferred for scale)

---

# CAPTCHA HANDLING RULE

If CAPTCHA is detected:

* STOP scraping immediately
* DO NOT attempt bypass
* Mark job as FAILED_REQUIRES_MANUAL_REVIEW

---

# DATA PRIVACY RULES

System MUST NOT:

* store personal sensitive data beyond business context
* collect private individual emails (non-business)
* extract personal profiles unrelated to business entity

Allowed:

* business emails (public-facing)
* business phone numbers
* official social pages

---

# EMAIL HANDLING RULES

## Allowed Emails

* info@
* contact@
* support@
* business inquiry addresses

---

## Forbidden Email Usage

System MUST NOT:

* attempt email verification via brute force
* scrape hidden email databases
* guess non-public emails

---

# SOCIAL PLATFORM RULES

Allowed:

* public profile scraping
* publicly visible posts metadata (light usage)
* follower counts (if visible)

Forbidden:

* login-based scraping
* private message extraction
* friend graph mining

---

# LEGAL COMPLIANCE GUIDELINES

System is designed for:

* lead generation from publicly available data
* business intelligence aggregation
* outreach optimization

NOT for:

* spam generation
* harassment campaigns
* mass unsolicited messaging abuse

---

# OUTREACH SAFETY RULES

LeadForge DOES NOT:

* send emails automatically
* send DMs automatically
* spam contact forms

It ONLY:

* identifies contact channels
* prioritizes outreach methods
* exports leads for manual or external CRM use

---

# STORAGE SECURITY

## Database Rules

* No sensitive personal data storage
* Encrypt sensitive configuration
* Do not store scraped HTML permanently (optional cleanup)

---

# SECRETS MANAGEMENT

MUST NOT:

* hardcode API keys
* store credentials in codebase

MUST USE:

* environment variables
* secret managers (production)

---

# API SECURITY RULES

* JWT required for all protected endpoints
* Rate limiting required
* Input validation mandatory
* No unvalidated query execution

---

# WORKER SECURITY RULES

Workers MUST:

* validate all inputs from queue
* sanitize scraped HTML
* reject malformed data
* log suspicious patterns

---

# SCRAPER SAFETY RULES

Each scraper MUST:

* have max depth limit
* have timeout enforcement
* respect concurrency caps
* avoid recursive traps

---

# ABUSE PREVENTION

System MUST detect:

* repeated scraping of same domain
* unusually high request patterns
* infinite job loops

If detected:

* throttle worker
* pause queue
* log incident

---

# MONITORING SECURITY EVENTS

Track:

* CAPTCHA triggers
* failed request spikes
* blocked IP patterns
* scraping bans (HTTP 403/429 spikes)

---

# INCIDENT RESPONSE

If system is blocked:

1. Stop affected worker
2. Reduce concurrency
3. Increase delay
4. Switch proxy pool (if available)
5. Resume gradually

---

# EXPORT SECURITY RULES

Exports MUST:

* only include business data
* exclude sensitive or personal fields
* never include scraped raw HTML
* respect lead filtering rules

---

# FRONTEND SECURITY RULES

Dashboard MUST:

* not expose internal worker logic
* not expose Redis or queue data
* not expose API secrets

---

# FINAL SECURITY PRINCIPLE

> If scaling the system requires aggressive scraping behavior, the system design is wrong.

LeadForge AI must remain:

* stable
* compliant
* slow enough to be safe
* intelligent enough to be useful

