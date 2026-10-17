# apps/web — schemawatch Dashboard

Real-time Vite + React + TypeScript web dashboard for **schemawatch**, an open-source API contract drift monitor.

## Features

- **Overview Dashboard**: High-level KPI stat cards, alerts-per-hour trend visualization (Recharts), and endpoint health table.
- **Alert Feed**: Contract drift audit log with severity filtering (`breaking`, `warning`, `info`), vendor filters, and acknowledgment actions.
- **Visual Diff Viewer**: Interactive side-by-side / inline diff viewer displaying baseline (`WAS`) vs observed payload shape (`NOW`).
- **Endpoint Detail & Schema Tree**: Interactive JSON schema tree displaying required property flags and baseline version history.
- **Schema Adoption**: Single-click "Accept New Schema" confirmation flow to adopt observed schemas as the new baseline.
- **Real-time Server-Sent Events (SSE)**: Streaming SSE bridge via `fetch` ReadableStream with authentication support, automatic backoff reconnection, live indicator, and toast alerts.
- **Dark & Light Mode**: Seamless theme switcher supporting system preference.
- **Session Authentication**: Bearer token management stored exclusively in `sessionStorage` and purged on 401.

## Tech Stack

- **Framework**: React 18 + TypeScript (strict mode, zero `any`)
- **Build Tool**: Vite
- **Styling**: Tailwind CSS + shadcn/ui inspired primitives
- **Client Routing**: React Router v6
- **Server State**: TanStack Query v5
- **Charts**: Recharts
- **API Client**: Generated with `openapi-typescript` + `openapi-fetch` from `apps/web/openapi.json`
- **Testing**: Vitest + Testing Library + MSW (Mock Service Worker)
- **Code Quality**: ESLint + Prettier

## Commands

```bash
npm install          # Install dependencies
npm run dev          # Run Vite development server (proxies /api to FastAPI)
npm run build        # Build static bundle to dist/
npm run test         # Run Vitest test suite
npm run typecheck    # Strict TypeScript check (tsc --noEmit)
npm run lint         # Run ESLint
npm run api:generate # Regenerate API types from openapi.json
```
