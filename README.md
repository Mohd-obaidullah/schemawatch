# schemawatch

Open-source API contract drift monitor. It learns the JSON response schema of third-party APIs from live traffic (no spec required) and alerts when that schema changes in a way that can break downstream systems (type change, missing field, new nullability, enum drift).

## Monorepo Layout

- `packages/core/`: Pure Python engine (`infer`, `diff`, `redact`, `severity`, `store`, `watchdog`).
- `apps/api/`: FastAPI server + CLI (M3/M5).
- `apps/web/`: Vite + React + TypeScript dashboard (M4).
- `deploy/`: Dockerfile & docker-compose manifests (M5).
- `docs/`: PRD, tech stack, and system design specifications.
- `examples/`: Demo scripts and mock vendors.

## Quickstart

```bash
uv sync
uv run python examples/demo.py
```

## Testing & Quality

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy packages/core
```

## License

MIT
