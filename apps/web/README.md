# LeadForge Web

Next.js 14 dashboard for the LeadForge backend.

## Stack

- **Framework**: Next.js 14 (App Router) + TypeScript
- **Styling**: Tailwind CSS + custom OKLCH palette
- **State**: Zustand (auth persistence)
- **HTTP**: Native fetch with JWT interceptor
- **Toasts**: sonner

## Aesthetic

Editorial / refined. Warm paper background, deep ink text, single ember accent.
Designed to avoid generic SaaS look — serif display type (Fraunces), monospace
metadata, hairline borders, lowercase status indicators.

## Setup

```bash
cd apps/web
npm install
cp .env.example .env.local   # set NEXT_PUBLIC_API_URL
npm run dev
```

The app runs on http://localhost:3000.

## Pages

| Route | Purpose |
|---|---|
| `/` | Marketing landing |
| `/register` | Account creation |
| `/login` | JWT login |
| `/dashboard` | Overview + recent activity |
| `/dashboard/jobs` | Search job list with filters |
| `/dashboard/jobs/new` | Create new discovery job |
| `/dashboard/businesses` | Discovered businesses (placeholder) |

## Auth

JWT tokens are persisted in `localStorage` via Zustand's `persist` middleware.
The dashboard layout gates routes client-side; the API enforces auth on
each request.

## API Base

Configured via `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
All requests go to `<api>/api/v1/*`.