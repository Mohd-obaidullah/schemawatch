# Phase 0: Core Hardening (M2.1) Progress Report

## Summary of Changes
Delivered core hardening per Phase 0 specifications:
1. **Slack Alert Colors**: Updated severity info color to blue (`#2F80ED`), keeping breaking red (`#E01E5A`) and warning yellow (`#ECB22E`).
2. **Lazy Exports & Zero-Httpx Core Import**: Converted hook and alert exports in `packages/core/schemawatch/__init__.py` to lazy properties via module `__getattr__` and `__dir__`, with static type definitions preserved under `TYPE_CHECKING`. Verified via subprocess test where `httpx` was blocked in `sys.modules`.
3. **DriftEvent Batched Dataclass**: Introduced frozen dataclass `DriftEvent(vendor, endpoint, changes: tuple[Change, ...], detected_at)` with `to_dict()` and `highest_severity`. Refactored `Watchdog.on_alert` to receive exactly ONE `DriftEvent` per observation. Updated `WebhookAlert`, `SlackAlert` (one message per event, header with vendor + endpoint, one coloured attachment per severity), `fan_out`, hook integrations, demo, tests, and `README.md`.
4. **Dynamic Map Privacy**: Hardened `redact.py` and `infer.py` with `is_dynamic_map` which treats objects as wildcard maps (`*`) when they have > 50 keys OR >= 50% of their keys (minimum 3) look like emails, UUIDs, long digits (>= 8 chars), or long hex strings (>= 16 chars). Proved that 5 email-keyed users never leak emails into baselines, alerts, or logs, while normal 8-field objects retain their property keys.
5. **Alert Retries & Hook Hardening**:
   - Webhook & Slack alerts retry on network errors (URLError/OSError) and HTTP 408/425/429/5xx with exponential backoff.
   - Non-retryable 4xx client errors (e.g. 400, 404) fail immediately without retries.
   - `Retry-After` header is honoured and capped at 30 seconds.
   - Injectable `sleep_fn` for fast deterministic testing.
   - HTTPX hook normalizes path segments (numeric, UUID, long hex to `{id}`) and includes HTTP method in endpoint key (e.g. `GET /v1/users/{id}`).
   - HTTPX hook inspects only 2xx JSON responses and skips bodies > `max_body_bytes`.
   - Thread worker `flush()` and `close()` verified.

## Files Changed
- `packages/core/schemawatch/__init__.py`: Lazy exports via `__getattr__`.
- `packages/core/schemawatch/diff.py`: Added frozen `DriftEvent` dataclass with `highest_severity` and `to_dict()`.
- `packages/core/schemawatch/redact.py`: Added `is_dynamic_key`, `is_dynamic_map` and updated `_redact_value`.
- `packages/core/schemawatch/infer.py`: Used `is_dynamic_map` for wildcard schema inference.
- `packages/core/schemawatch/watchdog.py`: Dispatches batched `DriftEvent` to `on_alert`.
- `packages/core/schemawatch/alerts/retry.py`: New retry helper handling status codes and `Retry-After` header.
- `packages/core/schemawatch/alerts/webhook.py`: Supports `DriftEvent`, status code filtering, exponential backoff, sleep injection.
- `packages/core/schemawatch/alerts/slack.py`: Header with vendor/endpoint, one attachment per severity with info blue, retries.
- `packages/core/schemawatch/alerts/__init__.py`: Updated `fan_out` to forward `DriftEvent`.
- `packages/core/schemawatch/integrations/httpx_hook.py`: Added endpoint normalization with method, 2xx filter, and max body bytes filter.
- `packages/core/tests/test_diff.py`: Added tests for `DriftEvent`.
- `packages/core/tests/test_alerts.py`: Added tests for multi-severity attachments, retries, `Retry-After`, and 404 abort.
- `packages/core/tests/test_integrations.py`: Added tests for normalization, 2xx filter, max body bytes filter.
- `packages/core/tests/test_lazy_import.py`: New test proving `import schemawatch` works without httpx installed.
- `packages/core/tests/test_privacy.py`: Added tests for 5-email users, 8-field normal object, UUID/digits/hex dynamic maps.
- `packages/core/tests/test_watchdog.py`: Updated for `DriftEvent` on `on_alert`.
- `examples/demo.py`: Verified.
- `examples/mock_vendor.py`: Updated `on_alert` callback to handle `DriftEvent`.
- `README.md`: Updated documentation with `DriftEvent` and dynamic map privacy.

## Commands Run and Results
- `uv run ruff check .`: Passed (0 errors).
- `uv run ruff format --check .`: Passed (36 files formatted).
- `uv run mypy packages/core`: Passed (0 errors in 25 source files, strict mode).
- `uv run pytest --cov=packages/core/schemawatch --cov-report=term-missing`: Passed 84 tests in 2.78s, **97% coverage**.
- `uv run python examples/demo.py`: Passed cleanly.
- `uv run python examples/mock_vendor.py`: Passed cleanly (2 breaking alerts captured).

## Deviations
None. All implementations follow AGENTS.md, docs, and Phase 0 instructions directly.

## What Could Not Be Verified
Real Slack webhook endpoints and live vendor APIs were not pinged (urllib mocked with real HTTP/network error semantics and payload verification in tests, per design).

## Open Questions
None.
