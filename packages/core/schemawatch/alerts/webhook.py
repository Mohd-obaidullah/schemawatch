from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from schemawatch.alerts.retry import should_retry_error
from schemawatch.diff import Change, DriftEvent

logger = logging.getLogger(__name__)


class WebhookAlert:
    """Fail-open generic webhook alert dispatcher with retries.

    Dispatches JSON alert payloads to a configured HTTP webhook endpoint.
    Guaranteed never to raise exceptions into the host application and never
    to log raw webhook URLs (preventing token/credential leaks).
    """

    def __init__(
        self,
        url: str,
        *,
        secret: str | None = None,
        headers: dict[str, str] | None = None,
        timeout: float = 5.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Invalid alert webhook URL scheme: {parsed.scheme!r}. Must be http or https."
            )
        self._url = url
        self._secret = secret
        self._headers = headers or {}
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep_fn = sleep_fn
        self.last_status_code: int | None = None
        self.last_response_body: str | None = None
        self.last_attempts: int = 0

    def __repr__(self) -> str:
        return f"WebhookAlert(url='***redacted***', timeout={self._timeout})"

    def __call__(self, event: DriftEvent | Change) -> None:
        """Dispatch drift event alert to the webhook."""
        self.send(event)

    def send(self, event: DriftEvent | Change) -> bool:
        """Send drift event alert with retries.

        Returns True if successful, False otherwise. Never raises exceptions.
        """
        # Normalize single Change to DriftEvent if passed directly
        if isinstance(event, Change):
            drift_event = DriftEvent(
                vendor="unknown",
                endpoint="unknown",
                changes=(event,),
            )
        else:
            drift_event = event

        payload: dict[str, Any] = {
            "event": "schema_drift",
            "vendor": drift_event.vendor,
            "endpoint": drift_event.endpoint,
            "highest_severity": drift_event.highest_severity,
            "detected_at": drift_event.detected_at,
            "changes": [c.to_dict() for c in drift_event.changes],
        }

        data = json.dumps(payload).encode("utf-8")
        req_headers = {
            "Content-Type": "application/json",
            "User-Agent": "schemawatch-alert/0.1.0",
            **self._headers,
        }
        if self._secret:
            sig = hmac.new(self._secret.encode("utf-8"), data, hashlib.sha256).hexdigest()
            req_headers["X-Schemawatch-Signature"] = f"sha256={sig}"

        self.last_status_code = None
        self.last_response_body = None
        self.last_attempts = 0

        for attempt in range(1, self._max_retries + 2):
            self.last_attempts = attempt
            try:
                req = urllib.request.Request(
                    self._url,
                    data=data,
                    headers=req_headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:  # nosec B310
                    self.last_status_code = resp.status
                    self.last_response_body = resp.read().decode("utf-8", errors="replace")
                    if 200 <= resp.status < 300:
                        return True
            except urllib.error.HTTPError as http_exc:
                self.last_status_code = http_exc.code
                try:
                    self.last_response_body = http_exc.read().decode("utf-8", errors="replace")
                except Exception:
                    self.last_response_body = None
                should_retry, retry_after = should_retry_error(http_exc)
                logger.warning(
                    "schemawatch: webhook delivery failed (attempt %d/%d): HTTP %d",
                    attempt,
                    self._max_retries + 1,
                    http_exc.code,
                )
                if not should_retry:
                    return False

                if attempt <= self._max_retries:
                    delay = (
                        retry_after
                        if retry_after is not None
                        else self._backoff * (2 ** (attempt - 1))
                    )
                    self._sleep_fn(delay)
            except Exception as exc:
                should_retry, retry_after = should_retry_error(exc)
                # Privacy rule: NEVER log the webhook URL
                logger.warning(
                    "schemawatch: webhook delivery failed (attempt %d/%d): %s",
                    attempt,
                    self._max_retries + 1,
                    type(exc).__name__,
                )
                if not should_retry:
                    return False

                if attempt <= self._max_retries:
                    delay = (
                        retry_after
                        if retry_after is not None
                        else self._backoff * (2 ** (attempt - 1))
                    )
                    self._sleep_fn(delay)

        logger.error(
            "schemawatch: webhook alert delivery exhausted all retries for %s %s",
            drift_event.vendor,
            drift_event.endpoint,
        )
        return False
