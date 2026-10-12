# schemawatch — Tech Stack

## 1. Core Stack
| Layer | Choice | Why |
| --- | --- | --- |
| Language and packaging | Python 3.12 (supports 3.10+), uv | Fast installs and lockfiles; Python is where target audience works |
| Core engine | Pure Python package, no heavy dependencies | Easy to embed as a library and easy to audit |
| HTTP client integration | httpx hooks, later requests and aiohttp | httpx supports sync and async with a clean hook API |
| API server | FastAPI + Uvicorn | Async and typed; its OpenAPI spec generates frontend client |
| Models and config | Pydantic v2 | Validation for config and API schemas |
| Fast state and dedupe | Redis 7 (redis-py) | Atomic SET NX with TTL for cooldown, fast counters |
| Durable database | PostgreSQL + SQLAlchemy 2.0 + Alembic; SQLite for quick local mode | Postgres is production standard; SQLite keeps try-it-out setup zero config |
| Background work | asyncio worker in-process; Redis Streams consumers in sidecar mode | Lighter than Celery and keeps validation off request path |
| Live updates | Server-Sent Events from FastAPI | One-way push of new alerts to dashboard without page refresh |
| Alerting | Generic webhooks and Slack incoming webhooks; email via SMTP later | Covers most teams with minimal code |
| CLI | Typer | Small, typed, good help output |
| Logging | structlog (JSON logs) | Easy to ship to any log platform |
| Observability | OpenTelemetry, Prometheus (prometheus-client), optional Sentry | What SRE teams expect from a production service |

## 2. Frontend
The dashboard is a Vite + React + TypeScript single-page app (SPA).

| Concern | Choice | Why |
| --- | --- | --- |
| Build tool | Vite | Fast dev server and simple static build |
| Framework | React + TypeScript | Industry standard, large contributor pool |
| Styling and components | Tailwind CSS + shadcn/ui | Clean, professional dashboards quickly |
| Routing | React Router | Standard client-side routing for the SPA |
| Server state | TanStack Query | Caching, polling and retries for API data |
| Live alerts | EventSource (SSE) | New drift events appear without refresh |
| Charts | Recharts | Time-series and health charts in React |
| Forms and validation | React Hook Form + Zod | Alert rules and settings forms |
| API client | Generated from FastAPI's OpenAPI spec (orval / openapi-typescript) | Frontend and backend types never drift apart |
| Tests | Vitest (unit), Playwright (end-to-end) | Fast component tests plus real browser flows |

## 3. Developer Tooling and Quality
| Area | Tool |
| --- | --- |
| Packaging | pyproject.toml with uv, published to PyPI |
| Python lint and format | ruff |
| Python type checking | mypy (strict on core package) |
| Python tests | pytest, pytest-asyncio, hypothesis |
| Frontend lint and format | ESLint, Prettier |
| Frontend tests | Vitest, Playwright |
| Git hooks | pre-commit |
| CI | GitHub Actions: lint, type check, Python tests on 3.10 to 3.13, frontend build |
| Containers | Dockerfile and docker-compose |
| Docs | MkDocs Material |
