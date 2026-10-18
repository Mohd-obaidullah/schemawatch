# Alerting Guide

`schemawatch` provides real-time drift alerting across multiple communication channels when third-party APIs deviate from established baseline contracts.

---

## 1. Slack Setup Walkthrough

### Step 1: Create a Slack App
1. Go to [api.slack.com/apps](https://api.slack.com/apps) in your browser.
2. Click **Create New App** &rarr; select **From scratch**.
3. Enter an App Name (e.g., `schemawatch`) and select your development workspace.

### Step 2: Enable Incoming Webhooks
1. In the left navigation sidebar under **Features**, select **Incoming Webhooks**.
2. Toggle the switch to **Activate Incoming Webhooks** (set to *On*).
3. Scroll down to the bottom of the page and click **Add New Webhook to Workspace**.
4. Choose the target channel where contract drift notifications should be posted (e.g., `#api-alerts` or `#dev-alerts`), then click **Allow**.

### Step 3: Copy Webhook URL
Copy the generated Webhook URL. It follows the format:
```text
https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

### Step 4: Configure schemawatch
Add the webhook URL to your environment or `.env` file:
```bash
SCHEMAWATCH_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

In Python code (httpx hook):
```python
import os
from schemawatch.alerts import SlackAlert

slack_alert = SlackAlert(
    webhook_url=os.environ["SCHEMAWATCH_SLACK_WEBHOOK_URL"],
    channel="#api-alerts",  # optional override
)
```

### Slack Alert Appearance
Alerts are grouped by severity with color coding:
- 🚨 **[BREAKING]** (Red `#E01E5A`): Type drift, missing required fields, removed fields.
- ⚠️ **[WARNING]** (Yellow `#ECB22E`): Enum drift, became nullable.
- ℹ️ **[INFO]** (Blue `#2F80ED`): Optional field added.

---

## 2. Generic Webhook Integration

`schemawatch` can post structured JSON alerts to any internal endpoint, PagerDuty, Datadog, or custom server.

### Configuration
```bash
SCHEMAWATCH_ALERT_WEBHOOK_URL="https://your-domain.com/api/webhooks/schemawatch"
SCHEMAWATCH_ALERT_WEBHOOK_SECRET="optional-hmac-shared-secret-here"
```

In Python code:
```python
from schemawatch.alerts import WebhookAlert

webhook_alert = WebhookAlert(
    url="https://your-domain.com/api/webhooks/schemawatch",
    secret="optional-hmac-shared-secret-here",  # Enables HMAC-SHA256 signature
    timeout=5.0,
    max_retries=2,
)
```

### Webhook Payload Schema

Each alert POSTs a JSON payload matching this schema:

```json
{
  "event": "schema_drift",
  "vendor": "stripe",
  "endpoint": "/v1/charges",
  "highest_severity": "breaking",
  "detected_at": 1700000000.0,
  "changes": [
    {
      "field": "$.customer.id",
      "kind": "type_changed",
      "severity": "breaking",
      "was": "string",
      "now": "integer",
      "detail": "string -> integer"
    },
    {
      "field": "$.amount_refunded",
      "kind": "field_missing",
      "severity": "breaking",
      "was": "integer",
      "now": null,
      "detail": "required field is missing"
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
|---|---|---|
| `event` | `string` | Fixed constant `"schema_drift"`. |
| `vendor` | `string` | Vendor or service identifier (e.g., `stripe`, `payco`). |
| `endpoint` | `string` | Monitored route or operation (e.g., `GET /v1/payments/{id}`). |
| `highest_severity` | `string` | Highest severity level among all changes in this event (`breaking`, `warning`, `info`). |
| `detected_at` | `float` | Unix epoch timestamp in UTC when drift was observed. |
| `changes` | `array` | List of detected individual schema modifications. |
| `changes[].field` | `string` | JSONPath to the altered field (`$.path.to.property`). |
| `changes[].kind` | `string` | Type of change (`type_changed`, `field_missing`, `field_added`, `became_nullable`, `enum_changed`). |
| `changes[].severity` | `string` | Severity rating: `breaking`, `warning`, or `info`. |
| `changes[].was` | `string \| null` | Previous expected type or representation in baseline. |
| `changes[].now` | `string \| null` | New observed type or representation. |
| `changes[].detail` | `string` | Human-readable explanation of the drift. |

> **Privacy Guarantee**: `changes[].was` and `changes[].now` contain only datatype names (`string`, `integer`, `boolean`, `null`), never real runtime values or customer data.

---

## 3. Optional HMAC-SHA256 Signature Verification

When `secret` (or `SCHEMAWATCH_ALERT_WEBHOOK_SECRET`) is configured, `schemawatch` includes an `X-Schemawatch-Signature` HTTP header on every webhook request:

```http
X-Schemawatch-Signature: sha256=d3b07384d113edec49eaa6238ad5ff00...
```

### Verification Example (Python / FastAPI)

```python
import hashlib
import hmac
from fastapi import FastAPI, HTTPException, Header, Request

app = FastAPI()
WEBHOOK_SECRET = "your-hmac-shared-secret-here"


@app.post("/api/webhooks/schemawatch")
async def receive_webhook(
    request: Request,
    x_schemawatch_signature: str = Header(None),
):
    body = await request.body()
    if not x_schemawatch_signature:
        raise HTTPException(status_code=401, detail="Missing signature header")

    expected_sig = (
        "sha256=" + hmac.new(WEBHOOK_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    )

    if not hmac.compare_digest(x_schemawatch_signature, expected_sig):
        raise HTTPException(status_code=401, detail="Invalid HMAC signature")

    payload = await request.json()
    print(
        f"Verified drift alert from {payload['vendor']} {payload['endpoint']}: {payload['highest_severity']}"
    )
    return {"status": "ok"}
```

---

## 4. Delivery Guarantees & Resiliency

- **Fail Open**: Alert delivery runs in background threads / async tasks and never crashes host requests or API ingestion.
- **Retry with Exponential Backoff**: Failed requests resulting from network disconnects, timeouts, or HTTP status codes `408`, `425`, `429`, and `5xx` are retried automatically.
- **Retry-After Support**: If a downstream service responds with `429 Too Many Requests` or `503 Service Unavailable` with a `Retry-After` header, schemawatch respects the delay (capped at 30 seconds).
- **Fan-Out Isolation**: When using `fan_out(slack_alert, webhook_alert)`, failure in one channel will never prevent delivery to other channels.
- **Cooldown Deduplication**: Identical drift events for the same field and change kind are suppressed during the cooldown window (default: 3600 seconds, configurable via `SCHEMAWATCH_COOLDOWN_SECONDS`).
- **Severity Filtering**: Alerts below `SCHEMAWATCH_MIN_ALERT_SEVERITY` (`info`, `warning`, `breaking`) are safely dropped.
- **Zero URL Logging**: Webhook URLs, query parameters, and secrets are never printed in application logs or exception traces.

---

## 5. One-Line cURL to Trigger a Test Alert

Run this command against a local schemawatch server with learned baseline to trigger a test breaking drift alert:

```bash
# Ingest breaking schema change (user_id changed from integer to string)
curl -s -X POST http://127.0.0.1:8000/api/ingest \
  -H "Authorization: Bearer <YOUR_SCHEMAWATCH_API_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"vendor":"payco","endpoint":"GET /v1/payments/{id}","payload":{"user_id":"string_instead_of_int","amount":10.5}}'
```

---

## 6. Running Real-Endpoint Integration Tests

Integration tests send live requests to real Slack incoming webhooks or webhook endpoints. They are marked `@pytest.mark.integration` and skipped by default.

To run them with your live test endpoints, provide the environment variables:

### Slack Integration Test:
```bash
SCHEMAWATCH_TEST_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL" uv run pytest -m integration -q
```

### Generic Webhook Integration Test:
```bash
SCHEMAWATCH_TEST_WEBHOOK_URL="https://webhook.site/your-unique-uuid" uv run pytest -m integration -q
```

### Both Channels Together:
```bash
SCHEMAWATCH_TEST_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..." SCHEMAWATCH_TEST_WEBHOOK_URL="https://webhook.site/..." uv run pytest -m integration -q
```
