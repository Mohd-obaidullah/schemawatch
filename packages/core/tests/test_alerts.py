from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

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


def _make_http_error(
    code: int, msg: str = "Error", headers: dict[str, str] | None = None
) -> urllib.error.HTTPError:
    from email.message import Message

    email_msg = Message()
    if headers:
        for k, v in headers.items():
            email_msg[k] = v
    return urllib.error.HTTPError(
        url="https://hooks.example.com",
        code=code,
        msg=msg,
        hdrs=email_msg,
        fp=io.BytesIO(b""),
    )


def test_webhook_alert_success() -> None:
    change = Change(
        path="$.user_id",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="integer",
        now="string",
        detail="integer -> string",
    )
    event = DriftEvent(
        vendor="payco",
        endpoint="/v1/payments",
        changes=(change,),
        detected_at=1700000000.0,
    )

    dispatcher = WebhookAlert("https://hooks.example.com/drift")

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        success = dispatcher.send(event)
        assert success is True
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        body = json.loads(req.data.decode("utf-8"))
        assert body["event"] == "schema_drift"
        assert body["vendor"] == "payco"
        assert body["endpoint"] == "/v1/payments"
        assert body["highest_severity"] == "breaking"
        assert body["detected_at"] == 1700000000.0
        assert len(body["changes"]) == 1
        assert body["changes"][0]["field"] == "$.user_id"


def test_webhook_alert_retries_network_error(caplog: pytest.LogCaptureFixture) -> None:
    change = Change(path="$.score", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="payco", endpoint="/v1/scores", changes=(change,))
    secret_url = "https://hooks.example.com/secret_token_12345"

    sleep_calls: list[float] = []
    dispatcher = WebhookAlert(
        secret_url,
        max_retries=2,
        backoff_seconds=0.1,
        sleep_fn=sleep_calls.append,
    )

    with patch("urllib.request.urlopen", side_effect=OSError("Connection refused")):
        success = dispatcher.send(event)
        assert success is False

    # Should attempt 3 times (1 initial + 2 retries) with exponential backoff: 0.1, 0.2
    assert len(sleep_calls) == 2
    assert sleep_calls[0] == pytest.approx(0.1)
    assert sleep_calls[1] == pytest.approx(0.2)

    # Privacy requirement: NEVER log the webhook URL
    all_logs = caplog.text
    assert secret_url not in all_logs
    assert "secret_token_12345" not in all_logs


def test_webhook_alert_retries_5xx_and_honours_retry_after() -> None:
    change = Change(path="$.score", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="payco", endpoint="/v1/scores", changes=(change,))

    sleep_calls: list[float] = []
    dispatcher = WebhookAlert(
        "https://hooks.example.com",
        max_retries=2,
        backoff_seconds=1.0,
        sleep_fn=sleep_calls.append,
    )

    # 429 with Retry-After: 12
    err_429 = _make_http_error(429, headers={"Retry-After": "12"})
    # 503 with Retry-After: 45 (should be capped at 30s)
    err_503 = _make_http_error(503, headers={"Retry-After": "45"})
    # Third attempt succeeds
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", side_effect=[err_429, err_503, mock_resp]):
        success = dispatcher.send(event)
        assert success is True

    assert len(sleep_calls) == 2
    assert sleep_calls[0] == 12.0
    assert sleep_calls[1] == 30.0  # Capped at 30 seconds


def test_webhook_alert_does_not_retry_non_retryable_4xx() -> None:
    change = Change(path="$.score", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="payco", endpoint="/v1/scores", changes=(change,))

    sleep_calls: list[float] = []
    dispatcher = WebhookAlert(
        "https://hooks.example.com",
        max_retries=3,
        backoff_seconds=1.0,
        sleep_fn=sleep_calls.append,
    )

    err_404 = _make_http_error(404, "Not Found")
    with patch("urllib.request.urlopen", side_effect=err_404) as mock_urlopen:
        success = dispatcher.send(event)
        assert success is False
        # Must NOT retry client errors like 404
        assert mock_urlopen.call_count == 1
        assert len(sleep_calls) == 0


def test_slack_alert_colors_and_fields() -> None:
    breaking_change = Change(
        path="$.id",
        kind=KIND_TYPE_CHANGED,
        severity=SEVERITY_BREAKING,
        was="int",
        now="str",
        detail="type drift",
    )
    warning_change = Change(
        path="$.status",
        kind="enum_changed",
        severity=SEVERITY_WARNING,
    )
    info_change = Change(
        path="$.opt",
        kind=KIND_FIELD_ADDED,
        severity=SEVERITY_INFO,
    )

    dispatcher = SlackAlert("https://hooks.slack.com/services/T00/B00/X00", channel="#alerts")

    # Multi-severity event produces one attachment per severity with correct colors
    event = DriftEvent(
        vendor="stripe",
        endpoint="/v1/charges",
        changes=(breaking_change, warning_change, info_change),
        detected_at=1700000000.0,
    )

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
        dispatcher(event)
        req = mock_urlopen.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))

        assert "stripe" in payload["text"]
        assert "/v1/charges" in payload["text"]
        assert payload["channel"] == "#alerts"

        attachments = payload["attachments"]
        assert len(attachments) == 3

        # Attachments ordered: breaking, warning, info
        assert attachments[0]["color"] == "#E01E5A"  # Breaking red
        assert "[BREAKING]" in attachments[0]["title"]
        assert attachments[1]["color"] == "#ECB22E"  # Warning yellow
        assert "[WARNING]" in attachments[1]["title"]
        assert attachments[2]["color"] == "#2F80ED"  # Info blue (hardened)
        assert "[INFO]" in attachments[2]["title"]


def test_slack_alert_retries_and_privacy(caplog: pytest.LogCaptureFixture) -> None:
    secret_slack_url = "https://hooks.slack.com/services/VERY_SECRET_KEY"
    sleep_calls: list[float] = []
    dispatcher = SlackAlert(
        secret_slack_url,
        max_retries=1,
        backoff_seconds=0.05,
        sleep_fn=sleep_calls.append,
    )

    change = Change(path="$.x", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="payco", endpoint="/v1", changes=(change,))

    with patch("urllib.request.urlopen", side_effect=OSError("Slack down")):
        success = dispatcher.send(event)
        assert success is False

    assert len(sleep_calls) == 1
    assert sleep_calls[0] == pytest.approx(0.05)
    assert secret_slack_url not in caplog.text
    assert "VERY_SECRET_KEY" not in caplog.text


def test_fan_out_resilience() -> None:
    dispatcher_1 = MagicMock()
    dispatcher_2 = MagicMock(side_effect=RuntimeError("Channel exploded"))
    dispatcher_3 = MagicMock()

    composite = fan_out(dispatcher_1, dispatcher_2, dispatcher_3)
    change = Change(path="$.amount", kind=KIND_TYPE_CHANGED, severity=SEVERITY_BREAKING)
    event = DriftEvent(vendor="stripe", endpoint="/v1/charges", changes=(change,))

    # Must invoke all dispatchers without raising
    composite(event)

    dispatcher_1.assert_called_once_with(event)
    dispatcher_2.assert_called_once_with(event)
    dispatcher_3.assert_called_once_with(event)


def test_alert_url_scheme_validation() -> None:
    # Scheme must be http or https; file:// and other schemes must raise ValueError
    with pytest.raises(ValueError, match="Invalid alert webhook URL scheme"):
        SlackAlert("file:///etc/passwd")

    with pytest.raises(ValueError, match="Invalid alert webhook URL scheme"):
        WebhookAlert("ftp://example.com/webhook")

    with pytest.raises(ValueError, match="Invalid alert webhook URL scheme"):
        WebhookAlert("javascript:alert(1)")
