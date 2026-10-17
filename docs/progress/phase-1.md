# Phase 1: API Server (M3) Progress Report

## Summary of Changes
1. **Missing Scripts Implemented**:
   - `apps/api/scripts/seed_demo.py`: Populates realistic vendors (Stripe, Twilio, SendGrid, GitHub), endpoints, versioned baselines, and drift events:
     - 1 breaking event (`kind="type_changed"`, Stripe `$.amount`)
     - 1 warning event (`kind="enum_changed"`, Twilio `$.status`)
     - 1 info event (`kind="field_added"`, SendGrid `$.ip_pool`)
     - 1 acknowledged event (`kind="became_nullable"`, GitHub `$.site_admin`)
     - Idempotent: skips seeding if records exist.
   - `apps/api/scripts/export_openapi.py`: Exports FastAPI OpenAPI 3.1 specification to `apps/web/openapi.json`.
2. **Tests Added**:
   - `apps/api/tests/test_scripts.py`: Verifies `export_openapi` schema, CLI invocation, `seed_demo_data` entity assertions, and idempotency.
   - `apps/api/tests/test_frontend_mount.py`: Verifies FastAPI mounts `apps/web/dist` at `/` with SPA fallback.

## Gate Results
- `uv run ruff check .`: Passed (0 errors)
- `uv run ruff format --check .`: Passed
- `uv run mypy packages/core`: Passed
- `uv run mypy apps/api`: Passed
- `uv run pytest`: Passed (119/119 tests passing)
