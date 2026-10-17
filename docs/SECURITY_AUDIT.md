# Security Audit Report — schemawatch

**Date:** October 17, 2026  
**Auditor:** schemawatch Lead Security Engineer  
**Scope:** Working tree, git history, `packages/core`, `apps/api`, `.github/workflows`, deployment configurations, and dependencies.

---

## 1. Executive Summary

A comprehensive security audit of the `schemawatch` repository was executed covering:
- **Secrets scanning:** Working tree and full git history.
- **Dependency audit:** Software supply chain analysis via `pip-audit`.
- **Static analysis:** SAST scan via Bandit and Ruff security rules.
- **API & Authentication:** Token comparison, route coverage, query parameter leak audit, error sanitization, input limits, and SSRF mitigations.
- **Privacy:** Verification of strict zero-raw-value persistence and logging rules.
- **Frontend & Deployment:** Security headers, Docker security, and CI/CD least-privilege review.
- **Repository Hygiene:** Security policies and gitignore hygiene.

No real secrets, credentials, or private keys were found in the working tree or full commit history. Several security enhancements and hardening measures were identified and categorized below.

---

## 2. Findings Summary Table

| ID | Title | Severity | File | Status |
|---|---|---|---|---|
| **SEC-01** | Token accepted in query parameter (`?token=`) | High | `apps/api/schemawatch_api/app.py` | Fixed |
| **SEC-02** | Incomplete `.gitignore` (missing `.env*`, `*.db`, `dist/`) | Medium | `.gitignore` | Fixed |
| **SEC-03** | Bandit B310: Webhook URL scheme validation (SSRF / Scheme Injection) | Medium | `packages/core/schemawatch/alerts/` | Fixed |
| **SEC-04** | Missing recursion depth limit for JSON payloads | Medium | `packages/core/schemawatch/redact.py`, `infer.py` | Fixed |
| **SEC-05** | Missing standard HTTP security headers (CSP, HSTS, frame-ancestors) | Medium | `apps/api/schemawatch_api/app.py` | Fixed |
| **SEC-06** | Missing prominent warning when `DEV_MODE=true` | Medium | `apps/api/schemawatch_api/app.py` | Fixed |
| **SEC-07** | Internal exception handling & debug sanitization | Medium | `apps/api/schemawatch_api/app.py` | Fixed |
| **SEC-08** | Bandit B104: Default bind address `0.0.0.0` in CLI | Medium | `apps/api/schemawatch_api/__main__.py` | Fixed |
| **SEC-09** | Missing least-privilege `permissions:` block in CI workflow | Medium | `.github/workflows/ci.yml` | Fixed |
| **SEC-10** | Missing `SECURITY.md` policy document | Medium | `SECURITY.md` | Fixed |
| **SEC-11** | Missing Dependabot configuration | Medium | `.github/dependabot.yml` | Fixed |
| **SEC-12** | Missing rate-limiting on `/api/ingest` | Low | `apps/api/schemawatch_api/app.py` | Fixed |
| **SEC-13** | Missing test asserting auth on all OpenAPI endpoints | Low | `apps/api/tests/test_auth.py` | Fixed |
| **SEC-14** | Missing `.env.example` template | Low | `.env.example` | Fixed |

---

## 3. Detailed Findings & Remediations

### SEC-01: Token accepted in URL query string (High)
- **File:** `apps/api/schemawatch_api/app.py`
- **Evidence:** `authenticate()` supported `token_query: str | None = Query(None, alias="token")`.
- **Risk:** Tokens in URLs leak into proxy access logs, browser history, referer headers, and server metrics.
- **Fix:** Remove query parameter fallback. Require `Authorization: Bearer <API_TOKEN>` header exclusively.

### SEC-02: Missing `.env*`, `*.db`, and cache rules in `.gitignore` (Medium)
- **File:** `.gitignore`
- **Evidence:** Local SQLite files (e.g. `schemawatch.db`) and local `.env` files were not ignored.
- **Risk:** Sensitive local configuration or runtime databases could be accidentally committed.
- **Fix:** Add `.env*`, `!.env.example`, `*.db`, `*.sqlite*`, `node_modules/`, and `dist/` to `.gitignore`.

### SEC-03: Webhook URL scheme validation (Medium)
- **File:** `packages/core/schemawatch/alerts/slack.py`, `webhook.py`
- **Evidence:** Bandit B310 flagged `urllib.request.urlopen` on arbitrary URLs without scheme checking.
- **Risk:** Potential SSRF or arbitrary protocol invocation (e.g., `file://`, `ftp://`).
- **Fix:** Validate that all alert webhook URLs strictly start with `https://` (or `http://` for local testing) before executing requests.

### SEC-04: Lack of recursion / nesting depth limit (Medium)
- **File:** `packages/core/schemawatch/redact.py`, `infer.py`
- **Evidence:** Nested structures were recursively processed without depth checks.
- **Risk:** Maliciously crafted payloads with 10,000+ nested brackets could trigger Python `RecursionError` and crash the worker.
- **Fix:** Enforce `DEFAULT_MAX_NESTING_DEPTH = 32` in `redact()` and `infer_schema()`, raising `PayloadTooLargeError` if exceeded.

### SEC-05: Missing HTTP security headers (Medium)
- **File:** `apps/api/schemawatch_api/app.py`
- **Evidence:** HTTP responses lacked CSP, X-Content-Type-Options, Referrer-Policy, and X-Frame-Options.
- **Risk:** Potential clickjacking, MIME sniffing, and script injection on the SPA dashboard.
- **Fix:** Add ASGI middleware setting:
  - `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `X-Frame-Options: DENY`

### SEC-06: Missing loud warning for `DEV_MODE=true` (Medium)
- **File:** `apps/api/schemawatch_api/app.py`
- **Evidence:** No logging warning emitted when server is initialized with `DEV_MODE=true`.
- **Risk:** Users may leave development mode enabled in staging or production without noticing authentication is bypassed.
- **Fix:** Emit prominent `WARNING` log alert upon application startup whenever `DEV_MODE=true`.

### SEC-07: Sanitized 500 error responses and explicit `debug=False` (Medium)
- **File:** `apps/api/schemawatch_api/app.py`
- **Evidence:** Server did not have explicit `debug=False` and a custom 500 handler.
- **Risk:** Internal server errors could leak tracebacks or file paths to clients.
- **Fix:** Set `debug=False` explicitly on FastAPI and add a global 500 exception handler returning a sanitized JSON payload.

### SEC-08: Default bind address `0.0.0.0` in CLI (Medium)
- **File:** `apps/api/schemawatch_api/__main__.py`
- **Evidence:** Bandit B104 flagged `--host` defaulting to `0.0.0.0`.
- **Risk:** Exposing development server to all local network interfaces by default.
- **Fix:** Set CLI default `--host` to `127.0.0.1` and require explicit `--host 0.0.0.0` for containerized environments.

### SEC-09: Least privilege permissions in CI workflow (Medium)
- **File:** `.github/workflows/ci.yml`
- **Evidence:** Workflow lacked top-level `permissions:` configuration.
- **Risk:** GitHub Actions tokens default to read/write in some repo settings.
- **Fix:** Add top-level `permissions: contents: read`.

### SEC-10: Missing `SECURITY.md` (Medium)
- **File:** `SECURITY.md`
- **Evidence:** No security disclosure guidelines or reporting contacts present.
- **Risk:** Security researchers have no private channel for reporting vulnerabilities.
- **Fix:** Create `SECURITY.md` with responsible disclosure instructions.

### SEC-11: Missing Dependabot configuration (Medium)
- **File:** `.github/dependabot.yml`
- **Evidence:** Dependabot configuration missing.
- **Risk:** Outdated vulnerable dependencies may go unnoticed.
- **Fix:** Create `.github/dependabot.yml` tracking Python packages and GitHub Actions.

### SEC-12: Rate limiting on `/api/ingest` (Low)
- **File:** `apps/api/schemawatch_api/app.py`
- **Evidence:** Ingestion endpoint had no client-side throttling.
- **Risk:** API abuse or denial of service by flooding ingest requests.
- **Fix:** Implement in-memory token-bucket sliding rate limiter on `/api/ingest`.

### SEC-13: OpenAPI route authentication test coverage (Low)
- **File:** `apps/api/tests/test_auth.py`
- **Evidence:** No automated test iterating over all OpenAPI schema endpoints.
- **Risk:** A newly added route could accidentally omit authentication dependencies.
- **Fix:** Add `test_all_openapi_routes_require_authentication_except_healthz` to `test_auth.py`.

### SEC-14: Missing `.env.example` (Low)
- **File:** `.env.example`
- **Evidence:** No template file documenting environment variables with safe defaults.
- **Risk:** Misconfiguration or committing real `.env` files.
- **Fix:** Create `.env.example` with non-sensitive placeholder values.

---

## 4. Verification Commands & Outputs

1. **Secrets Scan:**
   ```bash
   uv run python scripts/audit_scan.py
   ```
   *Result:* PASSED. Full git commit history and working tree scanned. Zero real secrets, tokens, or private keys detected.

2. **Dependency Supply Chain Audit:**
   ```bash
   uv run --with pip-audit pip-audit
   ```
   *Result:* PASSED. 0 vulnerabilities found across all dependencies.

3. **Bandit SAST Scan:**
   ```bash
   uv run --with bandit bandit -r packages/core/schemawatch apps/api/schemawatch_api -ll
   ```
   *Result:* PASSED. 0 Medium/High issues identified across 2,985 LOC.

4. **Linting:**
   ```bash
   uv run ruff check .
   ```
   *Result:* PASSED. All checks passed.

5. **Code Formatting:**
   ```bash
   uv run ruff format --check .
   ```
   *Result:* PASSED. 63 files inspected, 63 files properly formatted.

6. **Strict Type Checking:**
   ```bash
   uv run mypy packages/core apps/api
   ```
   *Result:* PASSED. Success: no issues found in 48 source files.

7. **Test Suite & Coverage:**
   ```bash
   uv run pytest --cov=schemawatch --cov=schemawatch_api --cov-report=term-missing
   ```
   *Result:* PASSED. 114 passed in 16.85s with 92% statement coverage across packages/core and apps/api.

