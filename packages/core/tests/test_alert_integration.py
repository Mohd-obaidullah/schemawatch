from __future__ import annotations

import os
import time

import pytest
from schemawatch.alerts.slack import SlackAlert
from schemawatch.alerts.webhook import WebhookAlert
from schemawatch.diff import Change, DriftEvent
from schemawatch.severity import (
    KIND_FIELD_ADDED,
    KIND_TYPE_CHANGED,
    SEVERITY_BREAKING,
    SEVERITY_INFO,
)


@pytest.mark.integration
def test_real_slack_alert_integration() -> None:
    """Send a real test alert to a Slack incoming webhook.

    Calls SlackAlert directly, asserts HTTP response is 200 with body 'ok',
    asserts delivery completes within timeout without needing retries, and asserts
    that on 4xx/5xx the sender reports failure rather than silently succeeding.
    Target URL is read ONLY from SCHEMAWATCH_TEST_SLACK_WEBHOOK_URL.
    Skipped if the environment variable is unset. Never prints or logs the webhook URL.
    """
    webhook_url = os.environ.get("SCHEMAWATCH_TEST_SLACK_WEBHOOK_URL")
    if not webhook_url:
        pytest.skip("SCHEMAWATCH_TEST_SLACK_WEBHOOK_URL is not set")

    dispatcher = SlackAlert(webhook_url, timeout=5.0, max_retries=1)
    change = Change(
        path="$.pricing_tier",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="string",
        now="object",
        detail="string -> object",
    )
    event = DriftEvent(
        vendor="stripe",
        endpoint="/v1/subscriptions",
        changes=(change,),
        detected_at=time.time(),
    )

    start_time = time.monotonic()
    success = dispatcher.send(event)
    duration = time.monotonic() - start_time

    assert success is True, "Slack alert delivery failed"
    assert dispatcher.last_status_code == 200, (
        f"Expected HTTP 200, got status {dispatcher.last_status_code}"
    )
    assert dispatcher.last_response_body is not None, "Expected response body from Slack"
    assert dispatcher.last_response_body.strip() == "ok", (
        f"Expected body 'ok', got: {dispatcher.last_response_body.strip()!r}"
    )
    assert dispatcher.last_attempts == 1, (
        f"Expected delivery on first attempt without retries, took {dispatcher.last_attempts}"
    )
    assert duration < 5.0, f"Delivery took {duration:.2f}s, exceeding 5.0s timeout limit"

    # Verify that on a 4xx error the sender reports failure rather than silently succeeding
    bad_dispatcher = SlackAlert(
        "https://hooks.slack.com/services/T00/B00/INVALID_TARGET_KEY",
        timeout=3.0,
        max_retries=0,
    )
    bad_success = bad_dispatcher.send(event)
    assert bad_success is False, "Slack sender must return False on HTTP error response"
    assert bad_dispatcher.last_status_code in (400, 403, 404), (
        f"Expected 4xx error code, got {bad_dispatcher.last_status_code}"
    )


@pytest.mark.integration
def test_real_webhook_alert_integration() -> None:
    """Send a real test alert to a generic HTTP webhook receiver.

    Calls WebhookAlert directly, asserts 2xx status, asserts delivery completes
    within timeout without retries, and asserts failure on invalid target.
    Target URL is read ONLY from SCHEMAWATCH_TEST_WEBHOOK_URL.
    Skipped if the environment variable is unset. Never prints or logs the webhook URL.
    """
    webhook_url = os.environ.get("SCHEMAWATCH_TEST_WEBHOOK_URL")
    if not webhook_url:
        pytest.skip("SCHEMAWATCH_TEST_WEBHOOK_URL is not set")

    dispatcher = WebhookAlert(webhook_url, timeout=5.0, max_retries=1)
    change = Change(
        path="$.metadata.region",
        kind=KIND_FIELD_ADDED,
        severity=SEVERITY_INFO,
        was=None,
        now="string",
        detail="New optional field added",
    )
    event = DriftEvent(
        vendor="payco",
        endpoint="/v1/payments",
        changes=(change,),
        detected_at=time.time(),
    )

    start_time = time.monotonic()
    success = dispatcher.send(event)
    duration = time.monotonic() - start_time

    assert success is True, "Failed to deliver real generic Webhook alert"
    assert dispatcher.last_status_code in (200, 201, 202, 204), (
        f"Expected 2xx status, got {dispatcher.last_status_code}"
    )
    assert dispatcher.last_attempts == 1, (
        f"Expected delivery on first attempt, took {dispatcher.last_attempts}"
    )
    assert duration < 5.0, f"Delivery took {duration:.2f}s, exceeding 5.0s timeout limit"

    # Verify failure handling on invalid target
    bad_dispatcher = WebhookAlert(
        "http://127.0.0.1:9/invalid-endpoint",
        timeout=1.0,
        max_retries=0,
    )
    bad_success = bad_dispatcher.send(event)
    assert bad_success is False, "Webhook sender must return False on connection failure"
