# schemawatch — Product Requirements Document (PRD)

Open source · Python · MIT license · Draft v0.1 · October 2026

schemawatch is an open-source API contract drift monitor. It learns the response schema of every third-party API from live traffic and alerts the moment that schema changes in a way that can break downstream systems.

## 1. Problem Statement
Companies, especially in FinTech and e-commerce, depend on dozens or hundreds of external APIs for payments, KYC, shipping, tax and banking. Vendors sometimes change response structures without notice: an integer becomes a string, a field disappears, a value becomes null. Downstream code (checkout, reconciliation, ledgers) then fails, often silently, and revenue leaks until someone notices.

Today, teams usually find out from customer complaints or error spikes, hours after the change shipped. Existing tools mostly need an OpenAPI spec or hand-written contract tests, which third-party vendors rarely provide or keep accurate.

## 2. Vision
Drop schemawatch into any Python service (or run it as a sidecar) and get a trustworthy, low-noise alert within minutes of a vendor changing an API response shape, with a clear diff that says what changed and how severe it is.

## 3. Goals and Non-goals

### Goals
- Learn schemas automatically from real traffic, with no spec required.
- Detect breaking changes: type change, missing field, new nullability, enum drift.
- Classify every change by severity (breaking, warning, info) to keep alerts meaningful.
- Add negligible latency to production calls (sampling plus async processing).
- Never persist sensitive values. Only payload shapes are stored.
- Be easy to adopt: one pip install and a few lines of code.

### Non-goals (v1)
- Full API testing, fuzzing or load testing.
- Validating business logic or the correctness of values.
- Monitoring request payloads (v1 focuses on responses).
- Being a general-purpose APM or logging platform.

## 4. Target Users and Personas
| Persona | Need | How schemawatch helps |
| --- | --- | --- |
| Backend engineer at a FinTech or e-commerce company | Know immediately when a vendor changes a payload | Library hook plus Slack alert with a field-level diff |
| SRE / platform engineer | Low-noise signals, no production overhead | Sampling, dedupe, Prometheus metrics, sidecar mode |
| Engineering manager / on-call lead | Fewer surprise outages from third parties | Dashboard with endpoint health and alert history |
| Open-source contributor | Small, well-scoped tasks to pick up | Plugin points for alert channels, diff rules and stores |

## 5. User Stories
- As a backend engineer, I add one hook to my HTTP client so every vendor call is observed without changing business code.
- As an on-call engineer, I get a Slack message saying `payco /v1/payments $.user_id: integer -> string (BREAKING)` instead of a vague error spike.
- As a platform engineer, I set a sampling rate and cooldown so alerts stay quiet and cheap.
- As a team lead, I open a dashboard and see which vendor endpoints are healthy, drifting or broken.
- As a developer, when a vendor change is intentional and safe, I run `schemawatch accept` to update the baseline.

## 6. Functional Requirements
Priority: P0 = must have for v0.1 release, P1 = v0.2 to v0.3, P2 = later.

| ID | Requirement | Priority |
| --- | --- | --- |
| F1 | Infer a schema from JSON payloads and merge multiple samples (types union, required-field intersection) | P0 |
| F2 | Learning phase: build a baseline per (vendor, endpoint) from the first N samples | P0 |
| F3 | Drift detection: type_changed, field_missing, field_added, became_nullable | P0 |
| F4 | Severity classification (breaking / warning / info) | P0 |
| F5 | PII-safe processing: values redacted before storage or alerting | P0 |
| F6 | Configurable sampling rate and alert cooldown (dedupe) | P0 |
| F7 | Redis-backed baseline and dedupe store, with in-memory fallback | P0 |
| F8 | httpx integration hook (sync and async clients) | P0 |
| F9 | Alert channels: console, generic webhook, Slack | P0 |
| F10 | REST API exposing endpoints, baselines and events | P1 |
| F11 | Web dashboard: stats, alert feed, diff viewer, acknowledge, endpoint health | P1 |
| F12 | CLI: schemawatch report, baseline show, accept | P1 |
| F13 | Enum drift detection (new or removed values) | P1 |
| F14 | Event history in a durable store (SQLite, then Postgres) | P1 |
| F15 | requests and aiohttp integrations; ASGI/WSGI proxy (sidecar) mode | P1 |
| F16 | Per-endpoint ignore rules (for example volatile fields) | P1 |
| F17 | Optional import of an existing OpenAPI or JSON Schema as the baseline | P2 |
| F18 | Prometheus metrics endpoint | P2 |
| F19 | Email, PagerDuty and Microsoft Teams alert channels | P2 |
| F20 | Format-level drift (date formats, ID patterns such as UUID vs numeric) | P2 |

## 7. Non-functional Requirements
- **Performance**: observation adds under 1 ms p99 on the request path (the heavy work runs off the hot path).
- **Reliability**: if Redis, the alert channel or the watchdog itself fails, the host application is never affected (fail open).
- **Privacy**: no raw values are stored, logged or alerted. Redaction happens before any persistence.
- **Portability**: Python 3.10 or newer, works with or without Redis.
- **Observability**: structured logs and metrics for the watchdog itself.
- **Quality**: at least 90% test coverage on infer, diff and redact modules.

## 8. Success Metrics
- Time to first alert after a simulated vendor change is under 60 seconds in the demo.
- False-positive rate of breaking alerts is under 2% on recorded real-world traffic fixtures.
- Setup takes under 10 minutes from pip install to first alert.
- Community: GitHub stars, external contributors and good first issue completion rate.
