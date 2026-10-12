AGENTS.md — schemawatch

Instructions for AI coding agents (Antigravity, Claude Code, Cursor, etc.) working in this repo. Read this file fully before making changes. Human contributors may find it useful too.

1. What this project is

schemawatch is an open-source API contract drift monitor. It learns the JSON response schema of third-party APIs from live traffic (no spec required) and alerts when that schema changes in a way that can break downstream systems (type change, missing field, new nullability, enum drift).

Primary audience: backend/platform engineers at FinTech and e-commerce companies. License: MIT. Language: Python (backend), TypeScript (frontend).

Source-of-truth docs live in docs/ (PRD, tech stack, system design). If code and docs disagree, stop and ask instead of guessing; do not silently change either.

2. Stack (do not add alternatives without asking)
Layer	Choice
Language / packaging	Python 3.12 (support 3.10+), uv
API	FastAPI + Uvicorn, Pydantic v2
Fast state / dedupe	Redis 7 (redis-py), with in-memory fallback
Database	PostgreSQL via SQLAlchemy 2.0 + Alembic; SQLite for local mode
HTTP integration	httpx event hooks first; requests/aiohttp later
CLI	Typer
Logging / metrics	structlog, prometheus-client
Frontend	Vite + React + TypeScript, Tailwind CSS, shadcn/ui, React Router, TanStack Query, Recharts, React Hook Form + Zod
API client	generated from FastAPI's OpenAPI spec (orval or openapi-typescript); never hand-write API types
Tests	pytest, pytest-asyncio, hypothesis; Vitest, Playwright
Quality	ruff, mypy (strict on packages/core), ESLint, Prettier, pre-commit
CI / deploy	GitHub Actions, Docker, docker-compose

3. Repository layout (target monorepo)
packages/core/      pure Python engine, pip-installable, minimal dependencies
  schemawatch/      infer.py diff.py redact.py severity.py store.py watchdog.py
                    integrations/ (httpx_hook.py)   alerts/ (webhook.py slack.py)
apps/api/           FastAPI server + CLI; serves apps/web/dist in production
apps/web/           Vite + React + TypeScript dashboard
deploy/             Dockerfile, docker-compose.yml
docs/               PRD, tech stack, system design, MkDocs site
examples/           demo.py, mock_vendor.py
prototype/          early prototype code to migrate (delete once migrated)

packages/core must NEVER import from apps/*. Dependencies point inward only.

4. Commands
bash
# Python (run from repo root)
uv sync                       # install deps
uv run pytest                 # run tests
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/core

# Frontend (apps/web)
npm install
npm run dev                   # Vite dev server, proxies /api to FastAPI
npm run build && npm run test
npx playwright test           # e2e

# Whole stack
docker compose -f deploy/docker-compose.yml up

If a command above does not exist yet, create it as part of the task instead of inventing a different one.

5. Hard rules (never violate)
Privacy first. Raw payload values must never be stored, logged, queued externally, or put in an alert. Redact in the very first processing step; only shapes (types, field paths) may persist. Any change touching redact.py or data persistence needs a test proving no raw value leaks.
Fail open. The monitor must never break or noticeably slow the host application. All hook code is wrapped so exceptions are logged and swallowed. Queue is bounded; under pressure, drop samples and count them.
No secrets in code. Webhook URLs, Redis/DB URLs, tokens come from environment variables.
No new dependency in packages/core without explicit approval (it must stay light).
No destructive changes (deleting files, force-pushing, rewriting history, dropping tables) without asking.
Do not invent features. Only build what the current task asks for. Note ideas in a TODO/issue instead.

6. Coding conventions
Python: type hints everywhere, from __future__ import annotations, small pure functions, docstrings on public API.
Prefer dataclasses/Pydantic models over loose dicts at module boundaries.
Severity levels are exactly: breaking, warning, info. Change kinds are: type_changed, field_missing, field_added, became_nullable (later: enum_changed). Do not rename these; the frontend depends on them.
integer is compatible with number; check bool before int (bool is a subclass of int in Python).
Frontend: function components + hooks, strict TypeScript (no any), data fetching only through TanStack Query, UI built from shadcn/ui primitives. Support light and dark themes.
Keep functions and files small; no clever one-liners. Comments explain why, not what.
Commit messages: Conventional Commits (feat:, fix:, test:, docs:, chore:).

7. Testing requirements
Every behaviour change ships with tests in the same change.
infer, diff, redact, severity: table-driven unit tests plus hypothesis property tests (e.g. a payload never drifts from a baseline built from itself; merge is order-independent).
Integrations: use httpx.MockTransport with a mock vendor that changes shape mid-stream.
Aim for >= 90% coverage on infer, diff, redact, severity.
Do not mark a task done while tests fail. Do not delete or weaken a test to make it pass; explain instead.

8. Workflow for every task
Restate the task and list the files you plan to touch. If anything is ambiguous, ask first.
Work in small steps; run lint, type-check and tests after each meaningful change.
Do only the requested milestone. No drive-by refactors.
At the end, report: what changed, how you verified it (commands + results), what you did NOT do, and open questions.
Leave the repo in a green state (lint, types, tests passing).

9. Milestones
ID	Scope	Status
M1	Monorepo scaffold, migrate prototype to packages/core, severity module, tests, CI	next
M2	httpx hook, webhook + Slack alerts, demo with mock vendor, README	planned
M3	FastAPI server (/api/endpoints, /api/events, ack, accept, SSE), SQLite/Postgres history	planned
M4	Vite + React dashboard wired to the API (pages: Overview, Alerts, Endpoint detail, Settings)	planned
M5	CLI, ignore rules, enum drift, Docker image, docs site, PyPI release	planned

Only the milestone named in the prompt is in scope.

10. Definition of done
Lint, type-check and all tests pass locally and in CI.
No raw values leak (privacy tests present for touched code).
Docs updated if behaviour, config or API changed (docs/ and README).
Final report written as described in section 8.
