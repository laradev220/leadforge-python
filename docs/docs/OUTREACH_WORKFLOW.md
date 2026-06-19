# OUTREACH_WORKFLOW.md

# LeadForge AI Outreach Workflow

Version: 1.0

Status: Approved

---

# Purpose

This document defines how businesses move through the LeadForge system from discovery to qualified outreach-ready lead.

This document does NOT define messaging campaigns.

This document defines lead lifecycle management.

---

# Core Philosophy

The platform exists to answer:

1. Who should we contact?
2. Why should we contact them?
3. How should we contact them?
4. In what order should we contact them?

Every workflow must support these objectives.

---

# Lead Lifecycle

```text
DISCOVERED
    ↓
ENRICHING
    ↓
ENRICHED
    ↓
SCORED
    ↓
QUALIFIED
    ↓
EXPORTED
```

---

# Stage 1: DISCOVERED

Definition:

Business has been identified.

Minimum Data:

* Name
* Category
* Address

Source Examples:

* Business directories
* Maps listings
* Public business records

Status:

```text
DISCOVERED
```

---

# Stage 2: ENRICHING

Definition:

Business is currently being processed.

Workers:

```text
Website Worker
Contact Worker
Social Worker
```

Possible Actions:

* Website discovery
* Website validation
* Contact discovery
* Social discovery

Status:

```text
ENRICHING
```

---

# Stage 3: ENRICHED

Definition:

All enrichment jobs completed.

Minimum Requirement:

At least one of:

```text
Website
Email
Phone
Contact Form
Social Profile
```

must exist.

OR

All enrichment attempts completed.

Status:

```text
ENRICHED
```

---

# Stage 4: SCORED

Definition:

Lead score generated.

Requirements:

```text
Lead Score
Grade
Best Contact Method
```

must exist.

Status:

```text
SCORED
```

---

# Stage 5: QUALIFIED

Definition:

Lead meets outreach criteria.

---

# Qualification Rules

Default Rules:

Lead Score:

```text
>= 80
```

AND

At least one contact channel exists.

Examples:

Valid:

```text
Score: 92
Facebook Found
```

Valid:

```text
Score: 85
Email Found
```

Invalid:

```text
Score: 90
No Contact Method
```

Status:

```text
QUALIFIED
```

---

# Stage 6: EXPORTED

Definition:

Lead has been included in an export.

Export Formats:

```text
CSV
XLSX
JSON
```

Status:

```text
EXPORTED
```

---

# Contact Method Selection

Purpose:

Determine the most effective outreach channel.

---

# Priority Matrix

Priority 1

```text
EMAIL
```

Reason:

Most scalable.

---

Priority 2

```text
CONTACT_FORM
```

Reason:

Official communication channel.

---

Priority 3

```text
WHATSAPP
```

Reason:

High response rates.

---

Priority 4

```text
LINKEDIN
```

Reason:

Professional outreach.

---

Priority 5

```text
FACEBOOK
```

Reason:

Strong small-business presence.

---

Priority 6

```text
INSTAGRAM
```

Reason:

Useful for local businesses.

---

Priority 7

```text
PHONE
```

Reason:

Fallback channel.

---

# Best Contact Method Algorithm

Example:

Business:

```text
Email Found
Facebook Found
Instagram Found
```

Result:

```text
EMAIL
```

---

Example:

Business:

```text
No Email
No Contact Form
Facebook Found
Instagram Found
```

Result:

```text
FACEBOOK
```

---

Example:

Business:

```text
Instagram Only
```

Result:

```text
INSTAGRAM
```

---

# Website Opportunity Workflow

Purpose:

Detect web-development prospects.

---

# Opportunity Level 1

No Website

Status:

```text
CRITICAL OPPORTUNITY
```

Lead Bonus:

```text
+40
```

---

# Opportunity Level 2

Website Exists

But:

```text
No SSL
No Contact Form
Poor Performance
```

Status:

```text
HIGH OPPORTUNITY
```

Lead Bonus:

```text
+25
```

---

# Opportunity Level 3

Modern Website

Status:

```text
LOW OPPORTUNITY
```

Lead Bonus:

```text
0
```

---

# Qualification Buckets

Purpose:

Help sales teams prioritize work.

---

# Tier A+

Score:

```text
95-100
```

Action:

```text
Immediate Outreach
```

Expected Volume:

Low

Expected Quality:

Exceptional

---

# Tier A

Score:

```text
90-94
```

Action:

```text
Within 24 Hours
```

---

# Tier B

Score:

```text
80-89
```

Action:

```text
Within 7 Days
```

---

# Tier C

Score:

```text
60-79
```

Action:

```text
Optional Outreach
```

---

# Tier D/F

Score:

```text
Below 60
```

Action:

```text
Archive
```

---

# Export Workflow

Purpose:

Generate sales-ready datasets.

---

# Export Filters

Supported:

```text
Minimum Score
Grade
Country
City
Category
Website Status
Best Contact Method
```

---

# Example Export

```text
Restaurants
No Website
Score > 85
Facebook Available
```

Output:

```text
Qualified Lead List
```

---

# Manual Review Workflow

Purpose:

Handle edge cases.

---

# Review Triggers

Low Confidence Website

```text
Website Confidence < 70
```

---

Multiple Website Candidates

```text
More than one possible website
```

---

Conflicting Contact Information

Example:

```text
Phone A
Phone B
Phone C
```

---

Result:

```text
Needs Manual Review
```

---

# Future CRM Workflow

Version 2

Potential Integrations:

```text
HubSpot
Salesforce
Pipedrive
Zoho
```

Workflow:

```text
Qualified Lead
        ↓
CRM Sync
        ↓
Sales Pipeline
```

---

# Future AI Workflow

Version 2

Generate:

```text
Lead Summary
Business Overview
Website Analysis
Outreach Recommendations
```

Example:

"This restaurant has over 150 reviews, an active Facebook page, and no website. Recommend offering online ordering and reservation functionality."

---

# Operational Rules

1. Every lead must have a lifecycle state.
2. Every lead must have a score.
3. Every lead must have a best contact method.
4. Every lead must be traceable back to discovery.
5. Outreach readiness must be deterministic.
6. Qualification rules must be configurable.
7. Exports must be reproducible.
8. Manual review cases must be identifiable.
9. Scoring and qualification are separate concepts.
10. Discovery volume is less important than qualified lead quality.

---

# Codex Rules

1. Model lead states explicitly.
2. Never skip lifecycle transitions.
3. Qualification must be rule-based.
4. Best contact method must be deterministic.
5. Preserve auditability.
6. Support future CRM integrations.
7. Support future AI enrichment.
8. Export only qualified data.
9. Keep workflows configurable.
10. Lead quality is the primary KPI.

```
```

