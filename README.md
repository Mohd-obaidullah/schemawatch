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
uv run python examples/mock_vendor.py
```

## HTTP Client Integration (httpx)

Integrate schemawatch into any `httpx.Client` or `httpx.AsyncClient` via non-blocking event hooks:

```python
import httpx
from schemawatch import Watchdog, create_httpx_hook
from schemawatch.alerts import SlackAlert, WebhookAlert, fan_out

# Configure alert dispatchers (receives DriftEvent with one message per observation)
alert_sink = fan_out(
    SlackAlert(webhook_url="https://hooks.slack.com/services/..."),
    WebhookAlert(url="https://my-backend.com/api/webhooks/schema-drift"),
)

# Initialize Watchdog monitor
watchdog = Watchdog(
    learning_threshold=10,
    sample_rate=0.05,
    on_alert=alert_sink,
)

# Attach non-blocking hook with bounded queue
hook = create_httpx_hook(
    watchdog=watchdog,
    vendor="stripe",
    endpoint="/v1/charges",
)

# Synchronous client
client = httpx.Client(event_hooks={"response": [hook.on_response]})
response = client.get("https://api.stripe.com/v1/charges")

# Asynchronous client
async_client = httpx.AsyncClient(event_hooks={"response": [hook.on_async_response]})
```

### Key Guarantees
- **Fail Open**: The hook and alert dispatchers swallow all internal exceptions and will never break host application requests.
- **Off the Hot Path**: Responses are copied to a bounded queue (`max_queue_size=1000`) and inferred in background threads. Under queue pressure, samples are dropped rather than delaying caller latency.
- **Batched Drift Events**: Observations emit a single `DriftEvent` containing all active changes, avoiding notification spam and grouping alerts by severity.
- **Privacy First**: Sensitive data is sanitized before storage or alerting. Dictionaries with > 50 distinct keys or >= 50% dynamic keys (emails, UUIDs, long digits, long hex) are hardened into wildcard maps (`$.*`), preventing PII or customer emails from persisting. Raw webhook URLs and tokens are never logged.

## Testing & Quality

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy packages/core
```

## License

MIT

