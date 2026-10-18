from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from collections.abc import Generator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest
from schemawatch.alerts import SlackAlert, WebhookAlert, fan_out
from schemawatch.diff import Change, DriftEvent
from schemawatch.severity import (
    KIND_FIELD_ADDED,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from schemawatch.store import MemoryStore
from schemawatch.watchdog import Watchdog
from schemawatch_api.config import Settings
from schemawatch_api.database import create_db_engine, create_session_factory, init_db
from schemawatch_api.service import SchemawatchService
from schemawatch_api.sse import SSEManager


class RecordedRequest:
    def __init__(self, path: str, headers: dict[str, str], body: bytes) -> None:
        self.path = path
        self.headers = {k.lower(): v for k, v in headers.items()}
        self.raw_headers = headers
        self.body = body
        self.json: dict[str, Any] | None = None
        if body:
            try:
                self.json = json.loads(body.decode("utf-8"))
            except Exception:
                self.json = None


class MockAlertReceiverServer(HTTPServer):
    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, MockAlertHandler)
        self.recorded_requests: list[RecordedRequest] = []
        self.queued_responses: list[tuple[int, dict[str, str], bytes]] = []
        self.delay_response_seconds: float = 0.0


class MockAlertHandler(BaseHTTPRequestHandler):
    server: MockAlertReceiverServer

    def log_message(self, format: str, *args: Any) -> None:
        pass  # Quiet down logging during test runs

    def do_POST(self) -> None:
        if self.server.delay_response_seconds > 0:
            time.sleep(self.server.delay_response_seconds)

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        self.server.recorded_requests.append(RecordedRequest(self.path, dict(self.headers), body))

        if self.server.queued_responses:
            status_code, headers, resp_body = self.server.queued_responses.pop(0)
            self.send_response(status_code)
            for k, v in headers.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(resp_body)
            return

        # Default 200 OK
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"ok"}')


@pytest.fixture
def mock_receiver() -> Generator[MockAlertReceiverServer, None, None]:
    """Start an ephemeral local mock HTTP server in a background thread."""
    server = MockAlertReceiverServer(("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2.0)


def test_mock_webhook_payload_and_headers(mock_receiver: MockAlertReceiverServer) -> None:
    port = mock_receiver.server_port
    secret = "hmac-shared-secret-test-1234"
    url = f"http://127.0.0.1:{port}/webhook-alert"

    dispatcher = WebhookAlert(url, secret=secret)

    change = Change(
        path="$.customer.card_token",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="string",
        now="integer",
        detail="string -> integer",
    )
    event = DriftEvent(
        vendor="payment_service",
        endpoint="/v1/charge",
        changes=(change,),
        detected_at=1700001234.0,
    )

    success = dispatcher.send(event)
    assert success is True
    assert len(mock_receiver.recorded_requests) == 1

    req = mock_receiver.recorded_requests[0]
    assert req.path == "/webhook-alert"
    assert req.headers.get("content-type") == "application/json"
    assert "schemawatch-alert" in req.headers.get("user-agent", "")

    # Verify HMAC-SHA256 signature
    sig_header = req.headers.get("x-schemawatch-signature", "")
    assert sig_header.startswith("sha256=")
    expected_sig = hmac.new(secret.encode("utf-8"), req.body, hashlib.sha256).hexdigest()
    assert sig_header == f"sha256={expected_sig}"

    # Verify payload format and data privacy: no raw values, only metadata
    body = req.json
    assert body is not None
    assert body["event"] == "schema_drift"
    assert body["vendor"] == "payment_service"
    assert body["endpoint"] == "/v1/charge"
    assert body["highest_severity"] == "breaking"
    assert body["detected_at"] == 1700001234.0
    assert len(body["changes"]) == 1
    ch_dict = body["changes"][0]
    assert ch_dict["field"] == "$.customer.card_token"
    assert ch_dict["kind"] == KIND_TYPE_CHANGED
    assert ch_dict["severity"] == SEVERITY_BREAKING
    assert ch_dict["was"] == "string"
    assert ch_dict["now"] == "integer"


def test_mock_slack_payload_and_colors(mock_receiver: MockAlertReceiverServer) -> None:
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/slack-webhook"

    dispatcher = SlackAlert(url, channel="#api-alerts")

    ch_breaking = Change(
        path="$.user.id",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="int",
        now="str",
    )
    ch_warning = Change(
        path="$.status",
        kind="enum_changed",
        severity=SEVERITY_WARNING,
    )
    ch_info = Change(
        path="$.new_feature",
        kind=KIND_FIELD_ADDED,
        severity=SEVERITY_INFO,
    )

    event = DriftEvent(
        vendor="auth0",
        endpoint="/oauth/token",
        changes=(ch_breaking, ch_warning, ch_info),
        detected_at=1700005678.0,
    )

    success = dispatcher.send(event)
    assert success is True
    assert len(mock_receiver.recorded_requests) == 1

    req = mock_receiver.recorded_requests[0]
    body = req.json
    assert body is not None
    assert body["channel"] == "#api-alerts"
    assert "auth0" in body["text"]
    assert "/oauth/token" in body["text"]

    attachments = body["attachments"]
    assert len(attachments) == 3
    # Check severity color mappings
    assert attachments[0]["color"] == "#E01E5A"  # Breaking red
    assert "[BREAKING]" in attachments[0]["title"]
    assert attachments[1]["color"] == "#ECB22E"  # Warning yellow
    assert "[WARNING]" in attachments[1]["title"]
    assert attachments[2]["color"] == "#2F80ED"  # Info blue
    assert "[INFO]" in attachments[2]["title"]


def test_mock_severity_filtering_in_service(mock_receiver: MockAlertReceiverServer) -> None:
    """Verify SCHEMAWATCH_MIN_ALERT_SEVERITY filters alert dispatching."""
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/alert-receiver"

    engine = create_db_engine("sqlite:///:memory:")
    session_factory = create_session_factory(engine)
    init_db(engine)

    # 1. Configured with min_alert_severity="warning"
    settings = Settings(
        database_url="sqlite:///:memory:",
        api_token="test-token-12345",
        dev_mode=True,
        alert_webhook_url=url,
        min_alert_severity="warning",
        learn_samples=1,
    )
    service = SchemawatchService(
        settings=settings,
        session_factory=session_factory,
        sse_manager=SSEManager(),
    )

    # Learn baseline
    service.ingest_payload("vendor_a", "/test", {"id": 1, "status": "active"})

    # Send an INFO drift (optional field added) -> Should be filtered out
    mock_receiver.recorded_requests.clear()
    service.ingest_payload("vendor_a", "/test", {"id": 1, "status": "active", "extra": "info_only"})
    assert len(mock_receiver.recorded_requests) == 0, "Info alert should be filtered out"

    # Send a BREAKING drift -> Should NOT be filtered out
    service.ingest_payload("vendor_a", "/test", {"id": "str_now", "status": "active"})
    assert len(mock_receiver.recorded_requests) == 1, "Breaking alert must be dispatched"


def test_mock_cooldown_dedup(mock_receiver: MockAlertReceiverServer) -> None:
    """Verify second identical alert within cooldown window is suppressed."""
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/cooldown-alerts"

    dispatcher = WebhookAlert(url)
    store = MemoryStore()
    watchdog = Watchdog(
        store=store,
        learning_threshold=1,
        cooldown_seconds=60,
        on_alert=dispatcher,
    )

    # Learn
    watchdog.observe("vendor_b", "/items", {"id": 1, "name": "widget"})

    # First drift observation
    mock_receiver.recorded_requests.clear()
    ch1 = watchdog.observe("vendor_b", "/items", {"id": "not_int", "name": "widget"})
    assert len(ch1) == 1
    assert len(mock_receiver.recorded_requests) == 1

    # Second identical drift observation within 60s cooldown -> Must be suppressed
    ch2 = watchdog.observe("vendor_b", "/items", {"id": "still_not_int", "name": "widget"})
    assert len(ch2) == 0
    assert len(mock_receiver.recorded_requests) == 1, "Identical alert must be suppressed"

    # Third distinct drift observation -> Must be dispatched
    ch3 = watchdog.observe(
        "vendor_b", "/items", {"id": "str", "name": 999}
    )  # name changed from string to integer
    assert len(ch3) == 1
    assert len(mock_receiver.recorded_requests) == 2, "Distinct field drift must be dispatched"


def test_mock_timeout_handling(mock_receiver: MockAlertReceiverServer) -> None:
    """Verify timeout handling fails open, retries, and never crashes."""
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/slow-receiver"

    # Set server to delay responses longer than client timeout
    mock_receiver.delay_response_seconds = 0.2
    dispatcher = WebhookAlert(
        url,
        timeout=0.05,
        max_retries=1,
        backoff_seconds=0.01,
    )

    change = Change(path="$.data", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="slow_vendor", endpoint="/slow", changes=(change,))

    success = dispatcher.send(event)
    assert success is False, "Slow endpoint should fail cleanly upon timeout"


def test_mock_retry_and_backoff_on_5xx_and_429(
    mock_receiver: MockAlertReceiverServer,
) -> None:
    """Verify retry on 5xx and 429 with Retry-After header."""
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/retry-endpoint"

    # Queue: 1) 429 Too Many Requests with Retry-After: 0.05
    #        2) 503 Service Unavailable
    #        3) 200 OK
    mock_receiver.queued_responses = [
        (429, {"Retry-After": "0.05", "Content-Type": "text/plain"}, b"Rate Limited"),
        (503, {"Content-Type": "text/plain"}, b"Service Unavailable"),
        (200, {"Content-Type": "application/json"}, b'{"status":"ok"}'),
    ]

    sleeps: list[float] = []
    dispatcher = WebhookAlert(
        url,
        max_retries=2,
        backoff_seconds=0.01,
        sleep_fn=sleeps.append,
    )

    change = Change(path="$.rate", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="rate_vendor", endpoint="/api", changes=(change,))

    success = dispatcher.send(event)
    assert success is True, "Should succeed on 3rd attempt after retrying 429 and 503"
    assert len(mock_receiver.recorded_requests) == 3
    assert len(sleeps) == 2
    # Verify Retry-After was honoured
    assert sleeps[0] == pytest.approx(0.05)


def test_mock_fan_out_resilience(mock_receiver: MockAlertReceiverServer) -> None:
    """Verify a failing alert channel never crashes ingestion or blocks the other channel."""
    port = mock_receiver.server_port
    working_url = f"http://127.0.0.1:{port}/working-channel"

    # Channel 1 points to a non-existent port (will fail connection)
    failing_dispatcher = WebhookAlert(
        "http://127.0.0.1:1/failing-channel", max_retries=0, timeout=0.1
    )
    # Channel 2 points to the active mock receiver
    working_dispatcher = WebhookAlert(working_url)

    composite = fan_out(failing_dispatcher, working_dispatcher)

    change = Change(path="$.status", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="multi_vendor", endpoint="/multi", changes=(change,))

    # Must complete cleanly without raising
    composite(event)

    # Channel 2 must have received the alert
    assert len(mock_receiver.recorded_requests) == 1
    assert mock_receiver.recorded_requests[0].path == "/working-channel"


def test_mock_privacy_and_url_redaction(
    mock_receiver: MockAlertReceiverServer, caplog: pytest.LogCaptureFixture
) -> None:
    """Verify webhook URLs and raw sensitive values are never leaked in logs or payloads."""
    port = mock_receiver.server_port
    secret_token = "ultra-secret-token-key-998877"
    url = f"http://127.0.0.1:{port}/webhook?secret={secret_token}"

    mock_receiver.queued_responses = [
        (500, {"Content-Type": "text/plain"}, b"Internal Server Error"),
    ]

    dispatcher = WebhookAlert(url, max_retries=0)

    # Payload with sensitive business/PII concepts
    raw_payload_with_pii = {
        "user_ssn": "123-45-6789",
        "credit_card": "4111-2222-3333-4444",
        "password_hash": "$2b$12$e8Y4vN2...",
        "amount": 1000000.0,
    }

    # Observe and create event through Watchdog to ensure redaction pipeline is active
    store = MemoryStore()
    watchdog = Watchdog(store=store, learning_threshold=1, on_alert=dispatcher)
    watchdog.observe("bank", "/account", {"amount": 100.0})

    with caplog.at_level(logging.WARNING):
        watchdog.observe("bank", "/account", raw_payload_with_pii)

    # Check 1: Webhook URL and secret token never appear in logs
    log_text = caplog.text
    assert secret_token not in log_text
    assert url not in log_text

    # Check 2: Repr redacts URL
    assert secret_token not in repr(dispatcher)
    assert "***redacted***" in repr(dispatcher)

    # Check 3: Sent payload contains zero raw values
    assert len(mock_receiver.recorded_requests) == 1
    sent_json = mock_receiver.recorded_requests[0].json
    assert sent_json is not None
    json_str = json.dumps(sent_json)
    assert "123-45-6789" not in json_str
    assert "4111-2222-3333-4444" not in json_str
    assert "$2b$12$e8Y4vN2..." not in json_str
    assert "1000000.0" not in json_str


def test_mock_slack_direct_delivery_and_error_reporting(
    mock_receiver: MockAlertReceiverServer,
) -> None:
    """Verify SlackAlert direct send, response tracking, and error reporting without swallowing."""
    port = mock_receiver.server_port
    url = f"http://127.0.0.1:{port}/slack-direct"

    # Scenario 1: Successful Slack webhook delivery returns 200 "ok"
    mock_receiver.queued_responses = [
        (200, {"Content-Type": "text/plain"}, b"ok"),
    ]
    dispatcher = SlackAlert(url, timeout=2.0, max_retries=1)
    event = DriftEvent(
        vendor="stripe",
        endpoint="/v1/charges",
        changes=(Change(path="$.amount", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING),),
    )

    success = dispatcher.send(event)
    assert success is True, "Slack direct delivery must succeed on 200 OK"
    assert dispatcher.last_status_code == 200
    assert dispatcher.last_response_body == "ok"
    assert dispatcher.last_attempts == 1

    # Scenario 2: 4xx Client error (e.g. 400 Bad Request) reports failure immediately without retry
    mock_receiver.queued_responses = [
        (400, {"Content-Type": "text/plain"}, b"invalid_payload"),
    ]
    bad_dispatcher = SlackAlert(url, timeout=2.0, max_retries=2)
    bad_success = bad_dispatcher.send(event)
    assert bad_success is False, "Slack sender must return False on 4xx error"
    assert bad_dispatcher.last_status_code == 400
    assert bad_dispatcher.last_response_body == "invalid_payload"
    assert bad_dispatcher.last_attempts == 1, "4xx errors must not trigger retries"
