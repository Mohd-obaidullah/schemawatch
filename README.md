<div align="center">

# schemawatch

**Catch silent third-party API changes before they break your checkout.**

schemawatch learns the JSON response schema of the APIs you depend on from live traffic (no spec required)
and alerts you the moment that schema changes in a way that can break your system.

   [![CI](https://github.com/Mohd-obaidullah/schemawatch/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Mohd-obaidullah/schemawatch/actions/workflows/ci.yml)![Python](https://img.shields.io/badge/python-3.10%20to%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

</div>

---

## Table of contents

- [Why schemawatch](#why-schemawatch)
- [Features](#features)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Quickstart](#quickstart)
- [Using it in your code (httpx)](#using-it-in-your-code-httpx)
- [Alert channels](#alert-channels)
- [API server](#api-server)
- [Run with Docker](#run-with-docker)
- [Web dashboard](#web-dashboard)
- [Configuration](#configuration)
- [Privacy and security](#privacy-and-security)
- [Architecture](#architecture)
- [Repository layout](#repository-layout)
- [Development](#development)
- [Roadmap](#roadmap)
- [FAQ](#faq)
- [Contributing](#contributing)
- [License](#license)

---

## Why schemawatch

Modern products depend on dozens of external APIs: payments, KYC, shipping, tax, banking. Vendors sometimes change
their response formats without telling you. A field that was a number becomes a string. A required field disappears.
A value that was never null suddenly is.

Your code does not crash at the vendor. It crashes **in your checkout, your ledger or your reconciliation job**, often
silently, and revenue leaks until someone notices. Most teams find out from customer complaints, hours later.

```text
Before:  { "user_id": 1042,      "amount": 10.5, "status": "ok" }
After:   { "user_id": "u_1042",                  "status": "ok" }

[BREAKING] payco GET /v1/payments/{id}  $.user_id  type_changed   integer -> string
[BREAKING] payco GET /v1/payments/{id}  $.amount   field_missing  required field is missing
```

Existing tools such as contract testing and spec-diffing generally need an API spec or a test environment. Vendors
rarely provide an accurate spec, and test environments do not show what production actually returns. schemawatch is
**passive and spec-free**: it watches real traffic and learns what "normal" looks like.

## Features

- **Learns from live traffic.** No OpenAPI file, no hand-written contract tests.
- **Detects the changes that break code:** type changes, missing fields, new nulls, and new fields.
- **Severity levels** (`breaking`, `warning`, `info`) so alerts stay meaningful.
- **Privacy first.** Raw values are redacted before anything is stored or sent. Only types and field paths persist.
- **Fail open.** A problem inside schemawatch never breaks or slows down your requests.
- **Non-blocking.** Work happens on a background thread behind a bounded queue.
- **Drop-in integration** for `httpx` (sync and async clients), plus a REST ingest API for any language.
- **Alert channels:** Slack (colored attachments) and a generic JSON webhook, with retries and timeouts.
- **Alert dedupe.** The same drift is announced once per cooldown window, not thousands of times.
- **API server and dashboard.** Endpoint health, drift history, diffs, acknowledge and "accept new schema" actions,
  live updates over Server-Sent Events.
- **Well tested.** Unit, property-based, privacy and integration tests; strict type checking; CI on every push.

## How it works

```text
 your app ──► httpx hook ──► bounded queue ──► worker thread
                                                   │
                       ┌───────────────────────────┘
                       ▼
        Redact ──► Infer shape ──► Learning phase? ──yes──► merge into baseline
        (drop values)               (first N samples)
                                          │ no
                                          ▼
                                 Sample (e.g. 5% of traffic)
                                          │
                                          ▼
                              Diff against baseline ──► Severity ──► Dedupe ──► Alert
```

1. **Hook.** A response hook copies each vendor response and enqueues it. If the queue is full, the sample is dropped.
2. **Redact.** Values are replaced with type-preserving placeholders at the very first step. Only the *shape* survives.
3. **Learn.** For every `(vendor, endpoint)`, the first N payloads are merged into a baseline schema. A field is
   required only if it appeared in every learning sample, so optional fields do not cause false alarms.
4. **Detect.** After learning, a configurable fraction of traffic is compared with the baseline.
5. **Classify.** Every change gets a severity.
6. **Alert.** One `DriftEvent` per observation is sent to your channels. Repeats are muted during the cooldown window.
7. **Decide.** If the vendor change is intentional, accept the new schema: the baseline gets a new version.

### What is detected

| Change kind | Meaning | Severity |
|---|---|---|
| `type_changed` | A field changed type, for example `integer` to `string` (`integer` is compatible with `number`) | breaking |
| `became_nullable` | A field that was never null is now `null` | breaking |
| `field_missing` (required) | A field present in every learning sample is gone | breaking |
| `field_missing` (optional) | A field that was only sometimes present is absent | info |
| `field_added` | A new field appeared | info |

Planned: opt-in enum drift (see [Roadmap](#roadmap)).

## Installation

Install from PyPI:

```bash
# Core monitoring engine
pip install schemawatch-core

# With httpx client hook
pip install "schemawatch-core[httpx]"

# Full FastAPI server and dashboard CLI
pip install schemawatch-api
```

Or install directly from GitHub:

```bash
pip install "git+https://github.com/Mohd-obaidullah/schemawatch.git#subdirectory=packages/core"
pip install "git+https://github.com/Mohd-obaidullah/schemawatch.git#subdirectory=apps/api"
```

In your code, import `schemawatch` (or `schemawatch_api`):

```python
import schemawatch
from schemawatch import Watchdog, create_httpx_hook
```

See [docs/RELEASING.md](docs/RELEASING.md) for the PyPI release and publishing walkthrough.

## Quickstart

**Requirements:** Python 3.10 or newer and [uv](https://docs.astral.sh/uv/). Node.js (LTS) is needed only to build the
dashboard.

```bash
git clone https://github.com/Mohd-obaidullah/schemawatch.git
cd schemawatch
uv sync
uv run python examples/demo.py
```

The demo learns a baseline from five normal payloads and then simulates a vendor change. Expected output:

```text
ALERT [BREAKING]: payco /v1/payments $.user_id: integer -> string (type_changed)
ALERT [BREAKING]: payco /v1/payments $.amount: required field is missing (field_missing)
```

Another demo runs a mock vendor behind an `httpx` client with the hook attached:

```bash
uv run python examples/mock_vendor.py
```

## Using it in your code (httpx)

```python
import httpx
from schemawatch import Watchdog, create_httpx_hook
from schemawatch.alerts import SlackAlert, WebhookAlert, fan_out

# 1. Where alerts go. fan_out sends to every channel; one failing channel never blocks the others.
alert_sink = fan_out(
    SlackAlert(webhook_url="https://hooks.slack.com/services/..."),
    WebhookAlert(url="https://my-backend.example.com/api/webhooks/schema-drift"),
)

# 2. The monitor: learn from the first 10 samples, then check 5% of traffic.
watchdog = Watchdog(
    learning_threshold=10,
    sample_rate=0.05,
    on_alert=alert_sink,
)

# 3. A non-blocking hook with a bounded queue.
hook = create_httpx_hook(
    watchdog=watchdog,
    vendor="stripe",
    endpoint="/v1/charges",
)

# Synchronous client
client = httpx.Client(event_hooks={"response": [hook.on_response]})
client.get("https://api.stripe.com/v1/charges")

# Asynchronous client
async_client = httpx.AsyncClient(event_hooks={"response": [hook.on_async_response]})
```

Your calling code does not change. Read secrets such as webhook URLs from environment variables, never from source code.

### Guarantees

| Guarantee | What it means |
|---|---|
| **Fail open** | The hook and every alert channel swallow internal exceptions. They never break a host request. |
| **Off the hot path** | Responses are copied onto a bounded queue (`max_queue_size=1000`) and processed in a background thread. Under pressure samples are dropped (counted in `hook.dropped_samples`), never waited for. |
| **One event per observation** | A single `DriftEvent` carries all changes found in that payload, so one vendor change is one notification, not twenty. |
| **Privacy first** | Values are redacted before storage or alerting. See [Privacy and security](#privacy-and-security). |

### Any language: REST ingest

Services that are not written in Python can post sampled payloads to the server. See [API server](#api-server).

## Alert channels

Every alert channel is a callable that receives a `DriftEvent` and can be passed as `on_alert`.

### Slack

`SlackAlert` posts to a Slack incoming webhook. The message header names the vendor and endpoint, and changes are
grouped into one colored attachment per severity, most urgent first:

| Severity | Color |
|---|---|
| breaking | red |
| warning | yellow |
| info | blue |

### Generic webhook

`WebhookAlert` posts JSON to any URL with a timeout and retries. The body includes the vendor, endpoint,
`highest_severity`, `detected_at` and the list of changes.

```json
{
  "vendor": "payco",
  "endpoint": "GET /v1/payments/{id}",
  "highest_severity": "breaking",
  "detected_at": "2026-10-17T10:42:00+00:00",
  "changes": [
    { "path": "$.user_id", "kind": "type_changed", "severity": "breaking", "detail": "integer -> string" }
  ]
}
```

### Delivery behaviour

- Network errors and HTTP `408`, `425`, `429` and `5xx` are retried with exponential backoff.
- Other `4xx` responses are not retried.
- A `Retry-After` header is honoured, up to a cap.
- Webhook URLs and tokens are never written to logs; only exception types are logged.

### Combining channels

```python
from schemawatch.alerts import fan_out

alert_sink = fan_out(slack_alert, webhook_alert)
```

## API server

The FastAPI server (`apps/api`) stores drift history, exposes it over REST and Server-Sent Events, and accepts payloads
from any language.

### Run it

```bash
# bash / zsh
export SCHEMAWATCH_DEV_MODE=true
uv run python apps/api/scripts/seed_demo.py     # optional: fills the database with demo data
uv run python -m schemawatch_api
```

```powershell
# Windows PowerShell
$env:SCHEMAWATCH_DEV_MODE="true"
uv run python apps/api/scripts/seed_demo.py
uv run python -m schemawatch_api
```

Open <http://127.0.0.1:8000/docs> for the interactive API documentation and <http://127.0.0.1:8000/> for the dashboard
(after building it, see below).

#### Security & API Tokens

`schemawatch` is **secure by default**. In production (`SCHEMAWATCH_DEV_MODE=false`), the server strictly requires a non-empty, non-placeholder API bearer token and fails fast on startup if one is not configured:

```bash
# Generate a cryptographically secure token
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set token and run in production mode
export SCHEMAWATCH_API_TOKEN="<generated-token>"
export SCHEMAWATCH_DEV_MODE="false"
uv run python -m schemawatch_api
```

Authenticate every API request using the standard HTTP Authorization header:
```http
Authorization: Bearer <SCHEMAWATCH_API_TOKEN>
```

> **Warning:** `SCHEMAWATCH_DEV_MODE=true` **disables authentication** and emits a loud startup warning. Never enable dev mode in production. For token rotation, reverse proxy / HTTPS termination, and CORS origin whitelisting, refer to [SECURITY.md](SECURITY.md).

### Try a live drift

Make the server learn quickly and check every request:

```bash
# bash / zsh
export SCHEMAWATCH_DEV_MODE=true SCHEMAWATCH_LEARN_SAMPLES=5 SCHEMAWATCH_SAMPLE_RATE=1.0
uv run python -m schemawatch_api
```

```powershell
# Windows PowerShell
$env:SCHEMAWATCH_DEV_MODE="true"
$env:SCHEMAWATCH_LEARN_SAMPLES="5"
$env:SCHEMAWATCH_SAMPLE_RATE="1.0"
uv run python -m schemawatch_api
```

In a second terminal send five normal payloads, then one where `user_id` became a string:

```bash
# bash / zsh
for i in 1 2 3 4 5; do
  curl -s -X POST http://127.0.0.1:8000/api/ingest -H "Content-Type: application/json" \
    -d "{\"vendor\":\"payco\",\"endpoint\":\"GET /v1/payments/{id}\",\"payload\":{\"user_id\":$i,\"amount\":10.5}}"
done

curl -s -X POST http://127.0.0.1:8000/api/ingest -H "Content-Type: application/json" \
  -d '{"vendor":"payco","endpoint":"GET /v1/payments/{id}","payload":{"user_id":"u_1","amount":10.5}}'
```

```powershell
# Windows PowerShell (use curl.exe to avoid PowerShell's Invoke-WebRequest alias)
1..5 | ForEach-Object {
  curl.exe -s -X POST http://127.0.0.1:8000/api/ingest -H "Content-Type: application/json" `
    -d "{`"vendor`":`"payco`",`"endpoint`":`"GET /v1/payments/{id}`",`"payload`":{`"user_id`":$_,`"amount`":10.5}}"
}

curl.exe -s -X POST http://127.0.0.1:8000/api/ingest -H "Content-Type: application/json" `
  -d '{"vendor":"payco","endpoint":"GET /v1/payments/{id}","payload":{"user_id":"u_1","amount":10.5}}'
```

Then open <http://127.0.0.1:8000/api/events> to see the `type_changed` event.

### Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/endpoints` | Monitored endpoints with health status |
| `GET` | `/api/endpoints/{id}/baseline` | Current baseline schema and version |
| `POST` | `/api/endpoints/{id}/accept` | Adopt the latest observed shape as the new baseline |
| `GET` | `/api/events` | Drift events (filters: severity, vendor, acknowledged, since) |
| `POST` | `/api/events/{id}/ack` | Acknowledge an event (`/unack` reopens it) |
| `GET` | `/api/stats` | Summary numbers for the dashboard |
| `GET` | `/api/config` | Read-only effective configuration (never returns secrets) |
| `POST` | `/api/ingest` | Submit a sampled payload from any language |
| `GET` | `/api/events/stream` | Server-Sent Events stream of new drift events |
| `GET` | `/healthz` | Health check (no auth) |

The authoritative, always-current reference is the generated OpenAPI documentation at `/docs`.

## Run with Docker

Run the complete schemawatch stack (API server, web dashboard, PostgreSQL, and automatic migrations) in a single command.

### Prerequisites

- **Docker Desktop** (Windows / macOS) or **Docker Engine with Docker Compose v2** (Linux) must be installed and running.

---

### Windows (PowerShell)

```powershell
# 1. Generate safe .env and cryptographic API token
.\scripts\setup.ps1

# 2. Build and start services in the background
docker compose up --build -d

# 3. Run automated smoke test
.\scripts\smoke-test.ps1

# View logs
docker compose logs --tail 50 schemawatch

# Stop services (database is preserved in named volume)
docker compose down

# Stop services and purge database volume
docker compose down -v
```

---

### macOS & Linux (Bash)

```bash
# 1. Generate safe .env and cryptographic API token
./scripts/setup.sh

# 2. Build and start services in the background
docker compose up --build -d

# 3. Run automated smoke test
./scripts/smoke-test.sh

# View logs
docker compose logs --tail 50 schemawatch

# Stop services (database is preserved in named volume)
docker compose down

# Stop services and purge database volume
docker compose down -v
```

> **Database Configuration Precedence:** The PostgreSQL connection in `docker-compose.yml` (`services.schemawatch.environment`) automatically takes precedence over the default SQLite setting in `.env`. No manual `.env` editing is required for Docker Compose.

---

### Troubleshooting

| Issue | Cause | Solution |
|---|---|---|
| `required variable SCHEMAWATCH_API_TOKEN is missing a value` | `.env` is missing or token is unset | Run `.\scripts\setup.ps1` (or `./scripts/setup.sh`) to generate `.env` with a token. |
| Container exits with `ERROR: SCHEMAWATCH_API_TOKEN is required` | Token is blank or placeholder `your-random-secure-token-here` | Set a valid token in `.env`: `python -c "import secrets; print(secrets.token_urlsafe(32))"`. |
| `.env` not recognized by Compose | `.env` was saved in the wrong directory | Ensure `.env` is directly in the project root next to `docker-compose.yml`. |
| Port 8000 already in use | Another process is bound to port 8000 | Run `PORT=8080 docker compose up` or terminate the conflicting process. |
| "Connection was aborted" / "Could not connect to server" | Container is starting up and applying database migrations | Run `docker compose ps` until `api-schemawatch-1` shows `(healthy)`. Initial migration takes 5–15s. |
| PowerShell `curl: The term 'curl' is not recognized` or syntax errors | Windows PowerShell aliases `curl` to `Invoke-WebRequest` | Always use `curl.exe` in PowerShell, or use `Invoke-RestMethod`. |
| `.env.txt` created instead of `.env` | Windows Notepad automatically appends `.txt` | Run `Rename-Item .env.txt .env`, or use `.\scripts\setup.ps1`. |

---

### SQLite Single Container

Run as a standalone container with a persisted SQLite volume:

```bash
docker build -t schemawatch .
docker volume create sw-data
docker run -d \
  --name schemawatch \
  -p 8000:8000 \
  -v sw-data:/data \
  -e SCHEMAWATCH_DATABASE_URL=sqlite:////data/schemawatch.db \
  -e SCHEMAWATCH_API_TOKEN=your-random-token \
  schemawatch
```

## Web dashboard

The dashboard (`apps/web`) is a Vite + React + TypeScript single-page app. Once built, the API server serves it at `/`.

```bash
# 1. Build the dashboard
cd apps/web
npm install
npm run build
cd ../..

# 2. Seed demo traffic and alerts (optional)
uv run python apps/api/scripts/seed_demo.py

# 3. Start the server; the dashboard is at http://127.0.0.1:8000
uv run python -m schemawatch_api
```

**Pages**

| Page | What you can do |
|---|---|
| Overview | Stat cards, alerts-per-hour chart, endpoint health table |
| Alerts | Filter by severity and vendor, view the was/now diff, acknowledge or reopen |
| Endpoint detail | See the baseline schema tree and drift history, and **accept the new schema** |
| Settings | Read-only view of the effective configuration |

New drift events appear live over Server-Sent Events. The app supports light and dark themes and works on small screens.

**Frontend development**

```bash
cd apps/web
npm install
npm run dev        # Vite dev server; proxies /api to the Python server
npm run lint && npm run typecheck && npm run test
```

## Configuration

The server is configured with environment variables prefixed `SCHEMAWATCH_`.

| Variable | Default | Description |
|---|---|---|
| `SCHEMAWATCH_API_TOKEN` | none | Bearer token required for all API calls (except `/healthz`) |
| `SCHEMAWATCH_DEV_MODE` | `false` | `true` disables authentication. **Local development only.** |
| `SCHEMAWATCH_DATABASE_URL` | SQLite file | Database connection URL (SQLite by default, PostgreSQL supported) |
| `SCHEMAWATCH_REDIS_URL` | none | Optional Redis for shared baselines and alert cooldown across instances |
| `SCHEMAWATCH_LEARN_SAMPLES` | `20` | Payloads used to build each baseline before checking starts |
| `SCHEMAWATCH_SAMPLE_RATE` | `0.05` | Fraction of traffic checked after learning (`1.0` checks everything) |
| `SCHEMAWATCH_COOLDOWN_SECONDS` | `3600` | Minimum time before the same alert can repeat |
| `SCHEMAWATCH_SLACK_WEBHOOK_URL` | none | Enables Slack alerts |
| `SCHEMAWATCH_ALERT_WEBHOOK_URL` | none | Enables generic webhook alerts |
| `SCHEMAWATCH_MIN_ALERT_SEVERITY` | `info` | Lowest severity that is sent to channels |

Run `GET /api/config` to see the effective values (booleans for which channels are configured; secrets are never shown).

## Privacy and security

schemawatch is designed to be safe to run next to payment and identity data.

- **No raw values are stored, logged or sent in alerts.** Redaction happens in the first processing step. Only types and
  field paths persist. Tests assert that sample secrets (SSNs, API keys, balances, notes) never appear in baselines or
  alert payloads.
- **Dynamic keys are scrubbed.** An object with more than 50 distinct keys, or where at least half of the keys look like
  emails, UUIDs, long digit strings or long hex strings, is treated as a map and its keys become `*`. Customer emails or
  IDs used as keys therefore never reach a baseline.
- **Fail open.** Errors in schemawatch are logged and swallowed; they never propagate to your application.
- **Bounded resources.** The queue is bounded, payload size and array length are limited, and samples are dropped
  rather than blocking your requests.
- **Authentication.** The server requires a bearer token unless `SCHEMAWATCH_DEV_MODE=true`.
- **Secrets.** Webhook URLs and tokens come from environment variables and are never logged.

Found a vulnerability? Please report it privately through GitHub Security Advisories on this repository rather than
opening a public issue.

## Architecture

```text
┌──────────────┐   sampled copy    ┌──────────────────────────────────────────┐
│ Your service │ ────────────────► │ schemawatch core (packages/core)         │
│ (httpx hook) │                   │ redact → infer → diff → severity → dedupe│
└──────────────┘                   └───────┬───────────────────────┬──────────┘
        ▲                                  │                       │
        │ POST /api/ingest                 ▼                       ▼
┌───────┴──────┐                  ┌─────────────────┐     ┌─────────────────┐
│ Other langs  │ ───────────────► │ Store           │     │ Alert channels  │
└──────────────┘                  │ SQL + Redis     │     │ Slack / webhook │
                                  └────────┬────────┘     └─────────────────┘
                                           ▼
                              ┌─────────────────────────┐
                              │ FastAPI (apps/api)      │ ◄── Dashboard (apps/web)
                              │ REST + SSE              │
                              └─────────────────────────┘
```

**Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Redis (optional), httpx · React, TypeScript, Vite, Tailwind CSS,
shadcn/ui, TanStack Query, Recharts · pytest, Hypothesis, Vitest, Playwright, ruff, mypy (strict), GitHub Actions.

Design documents live in [`docs/`](docs/): product requirements, tech stack and system design.

## Repository layout

```text
schemawatch/
├── packages/core/    Pure Python engine: infer, diff, redact, severity, store, watchdog, httpx hook, alerts
├── apps/api/         FastAPI server (REST, SSE, ingest, persistence) and scripts
├── apps/web/         Vite + React + TypeScript dashboard
├── deploy/           Docker and compose manifests
├── docs/             PRD, tech stack and system design
├── examples/         demo.py and mock_vendor.py
└── .github/          CI workflows
```

`packages/core` has no dependency on the apps and keeps its dependencies minimal; `httpx` and `redis` are optional extras.

## Development

```bash
uv sync                                   # install Python dependencies

uv run pytest                             # tests with coverage
uv run ruff check .                       # lint
uv run ruff format --check .              # formatting
uv run mypy packages/core                 # strict type checking
```

Frontend checks run from `apps/web`: `npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`.

Continuous integration runs the Python suite on Python 3.10 to 3.13 and the frontend lint, type-check, tests and build
on every push and pull request. Coverage must stay at or above 90%.

## Roadmap

**Done**

- Core engine: inference, diff, severity, redaction, stores and the `Watchdog`
- httpx hook (sync and async), Slack and webhook alerts, `DriftEvent` batching
- API server with history, SSE and ingest
- Web dashboard
- Docker multi-stage container and docker-compose stack (PostgreSQL, optional Redis, auto-migrations, non-root)

**Next**

- Command-line interface (`schemawatch endpoints`, `events`, `accept`, `demo`)
- Per-endpoint ignore rules for volatile fields
- Opt-in enum drift detection for explicitly listed fields
- `requests` integration

**Later**

- Documentation site, PyPI release
- Prometheus metrics

## FAQ

**Does it slow down my requests?**
No. The hook only copies the response body and enqueues it. Parsing, inference, diffing and alert delivery run on a
background thread, and a full queue drops samples instead of waiting.

**Will it leak customer data?**
Values are redacted before anything is stored or sent, and tests enforce this. Only types and field paths are kept.

**How is this different from Pact, Schemathesis, Optic or Postman monitors?**
Those tools mostly rely on a provided spec or on scheduled, scripted tests. schemawatch watches real production traffic and
needs no spec. It complements contract testing rather than replacing it.

**What if the vendor change is intentional?**
Use **Accept new schema** on the endpoint page (or `POST /api/endpoints/{id}/accept`). The baseline moves to a new version
and the related alerts are acknowledged.

**Too many alerts?**
Lower the sample rate, raise `SCHEMAWATCH_MIN_ALERT_SEVERITY`, and increase the cooldown. Only `breaking` changes are
likely to need a page.

## Contributing

Contributions are welcome: new alert channels, integrations, diff rules and documentation fixes.

1. Fork the repository and create a branch (`feat/...` or `fix/...`).
2. Run the checks listed in [Development](#development).
3. Open a pull request. CI must pass before it can be merged.

Please add tests with every behaviour change, and never log or store raw payload values.

## License

[MIT](LICENSE)

