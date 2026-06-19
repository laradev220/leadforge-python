# LeadForge AI Lead Scoring Engine

Version: 1.0

Status: Approved

Purpose:

Convert raw business data into actionable sales opportunities.

---

# Philosophy

Lead score does NOT measure:

- Business quality
- Revenue
- Popularity

Lead score measures:

> Likelihood that a business could benefit from website development, software services, digital transformation, SEO, automation, or online presence improvements.

Higher score = Better prospect.

---

# Final Score Formula

Lead Score Range:

0-100

Formula:

Final Score =
Website Opportunity Score +
Contact Availability Score +
Social Activity Score +
Business Validation Score +
Review Signal Score

Maximum:

100

Minimum:

0

---

# Scoring Categories

| Category | Max Points |
|-----------|------------|
| Website Opportunity | 40 |
| Contact Availability | 20 |
| Social Activity | 20 |
| Business Validation | 10 |
| Review Signals | 10 |

Total:

100

---

# Website Opportunity Score

Maximum:

40 Points

---

## No Website

Condition:

website_status = NOT_FOUND

Points:

+40

Reason:

Highest probability website-development lead.

---

## Website Exists But Weak

Conditions:

- No SSL
- No contact form
- Very slow
- Broken pages

Points:

+25

---

## Website Exists But Outdated

Conditions:

- Mobile issues
- Poor UX indicators
- Minimal content

Points:

+15

---

## Modern Website

Conditions:

- SSL
- Contact form
- Responsive
- Healthy

Points:

0

Reason:

Lower website-development opportunity.

---

# Contact Availability Score

Maximum:

20 Points

Purpose:

Businesses with reachable public channels are easier to convert.

---

## Public Email Found

+10

Examples:

info@
hello@
contact@

---

## Contact Form Found

+8

---

## WhatsApp Found

+8

---

## LinkedIn Available

+5

---

## Facebook Available

+4

---

## Instagram Available

+4

---

## Phone Available

+2

---

Cap:

20

---

# Social Activity Score

Maximum:

20 Points

Purpose:

Businesses active online are generally more responsive.

---

## Highly Active

Conditions:

Activity within last 30 days

+20

---

## Moderately Active

Conditions:

Activity within last 90 days

+12

---

## Low Activity

Conditions:

Activity within last 180 days

+5

---

## Inactive

Conditions:

No recent activity

0

---

# Business Validation Score

Maximum:

10 Points

Purpose:

Validate that the business is legitimate.

---

## Phone Present

+2

---

## Website Present

+2

---

## Social Profile Present

+2

---

## Address Present

+2

---

## Reviews Present

+2

---

Cap:

10

---

# Review Signal Score

Maximum:

10 Points

Purpose:

Measure whether the business is established.

---

## Review Count

1-10 Reviews

+2

---

11-50 Reviews

+5

---

51-200 Reviews

+8

---

200+ Reviews

+10

---

# Contact Method Ranking

The system must determine:

best_contact_method

for every business.

---

# Priority Order

1. EMAIL
2. CONTACT_FORM
3. WHATSAPP
4. LINKEDIN
5. FACEBOOK
6. INSTAGRAM
7. PHONE

---

# Example

Business:

Restaurant

Attributes:

- No Website
- Facebook Active
- Instagram Active
- Phone Present
- 120 Reviews

Scoring:

Website Opportunity:
40

Contact Availability:
10

Social Activity:
20

Business Validation:
10

Review Signal:
8

Total:

88

Grade:

A

Best Contact:

Facebook

---

# Example

Business:

Software Company

Attributes:

- Modern Website
- Contact Form
- LinkedIn
- Active

Scoring:

Website Opportunity:
0

Contact Availability:
15

Social Activity:
20

Business Validation:
10

Review Signal:
10

Total:

55

Grade:

D

Reason:

Low opportunity.

---

# Grade System

A+

95-100

Exceptional Prospect

---

A

90-94

Very Strong Prospect

---

B

80-89

Strong Prospect

---

C

60-79

Moderate Prospect

---

D

40-59

Weak Prospect

---

F

0-39

Poor Prospect

---

# Outreach Recommendations

A+

Immediate outreach.

---

A

Outreach within 24 hours.

---

B

Outreach within 7 days.

---

C

Low priority.

---

D

Optional.

---

F

Ignore.

---

# Future Scoring Signals

Version 2 may include:

- Website performance audits
- AI website quality analysis
- SEO indicators
- Google review sentiment
- Technology detection
- Booking systems
- E-commerce presence
- Advertising signals

These must be additive and not break existing scoring.

---

# Score Recalculation Rules

Recalculate when:

- Website changes
- New contacts discovered
- Social profiles discovered
- Reviews updated
- Manual refresh triggered

---

# Codex Rules

1. Scoring must be deterministic.
2. Same input must always produce same score.
3. No random factors.
4. Every score component must be explainable.
5. Store score breakdown.
6. Store best contact method.
7. Recalculate on enrichment updates.
8. Support future scoring modules.
9. Maximum score is 100.
10. Lead score is a business opportunity score, not a business quality score.
