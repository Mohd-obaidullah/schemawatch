# Phase 2: Dashboard (M4) Progress Report

## Summary of Changes
1. **Frontend Application Scaffolded in `apps/web`**:
   - Stack: Vite, React 18, TypeScript (strict mode, zero `any`), Tailwind CSS, Lucide icons.
   - Client routing via React Router v6.
   - Server state caching & invalidation via TanStack Query v5.
   - Real-time alerts activity visualization via Recharts.
   - Theme toggle (Light, Dark, System) with instant synchronization.
2. **Type-Safe API Client**:
   - Generated client types from `apps/web/openapi.json` using `openapi-typescript` + `openapi-fetch` (`npm run api:generate`).
   - Dynamic `baseUrl` resolving to current host or dev proxy.
   - Auth middleware injecting `Authorization: Bearer <token>` from `sessionStorage` and purging credentials on 401.
3. **Real-Time Streaming (`src/api/sse.ts`)**:
   - `fetch`-based SSE streaming client with `ReadableStream` (`body.getReader()`) supporting auth headers.
   - Exponential backoff auto-reconnect (1s–16s).
   - Invalidation of TanStack queries (`events`, `stats`, `endpoints`) on new events.
   - Real-time toast notifications with severity styling.
   - Live connection indicator in the navigation bar (`LIVE` / `Reconnecting` / `Offline`).
4. **Pages & Components**:
   - `TokenPage.tsx`: Bearer token input and dev-mode bypass indicator stored in `sessionStorage` only.
   - `OverviewPage.tsx`: 4 stat cards, alerts-per-hour activity chart (Recharts), and endpoints health table.
   - `AlertsPage.tsx`: Severity filter chips, vendor filter dropdown, include-acknowledged toggle, pagination, and Acknowledge/Reopen mutations.
   - `DiffViewer.tsx`: Side-by-side / inline display of field paths, mutation kinds, expected shape (`WAS`), and observed drift (`NOW`).
   - `EndpointDetailPage.tsx`: Endpoint metadata, `SchemaTree` with `*required` property marks, drift history audit log, and "Accept New Schema" confirmation dialog.
   - `SettingsPage.tsx`: Read-only `/api/config` view of detection parameters, storage type, and alert dispatch channels (zero secrets/URLs leaked).
5. **Testing & Quality**:
   - 6 Vitest test suites with Mock Service Worker (MSW) mocking all API endpoints.
   - Dedicated `web` CI job added to `.github/workflows/ci.yml`.

## Gate Results
- `npm run typecheck`: Passed (`tsc --noEmit` exit code 0)
- `npm run lint`: Passed (0 warnings, 0 errors)
- `npm run test`: Passed (6/6 test files, 10/10 tests)
- `npm run build`: Passed (`dist/` generated)
