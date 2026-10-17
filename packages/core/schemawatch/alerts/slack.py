from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

from schemawatch.alerts.retry import should_retry_error
from schemawatch.diff import Change, DriftEvent
from schemawatch.severity import SEVERITY_BREAKING, SEVERITY_INFO, SEVERITY_WARNING

logger = logging.getLogger(__name__)

SLACK_COLOR_MAP: dict[str, str] = {
    SEVERITY_BREAKING: "#E01E5A",  # Red / Danger
    SEVERITY_WARNING: "#ECB22E",  # Yellow / Warning
    SEVERITY_INFO: "#2F80ED",  # Blue / Info
}
SLACK_COLOR_DEFAULT = "#2F80ED"  # Blue / Info


class SlackAlert:
    """Fail-open Slack incoming webhook dispatcher with rich formatting.

    Maps schema drift changes to colored Slack attachments.
    Never raises exceptions into host application and never logs raw webhook URLs.
    """

    def __init__(
        self,
        webhook_url: str,
        *,
        channel: str | None = None,
        timeout: float = 5.0,
        max_retries: int = 2,
        backoff_seconds: float = 0.5,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._url = webhook_url
        self._channel = channel
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff = backoff_seconds
        self._sleep_fn = sleep_fn

    def __call__(self, event: DriftEvent | Change) -> None:
        """Dispatch drift event alert to Slack."""
        self.send(event)

    def _build_payload(self, event: DriftEvent) -> dict[str, Any]:
        header_text = f":warning: API Contract Drift Detected: *{event.vendor}* `{event.endpoint}`"

        # Group changes by severity in priority order
        severity_order = [SEVERITY_BREAKING, SEVERITY_WARNING, SEVERITY_INFO]
        changes_by_sev: dict[str, list[Change]] = {sev: [] for sev in severity_order}

        for ch in event.changes:
            if ch.severity in changes_by_sev:
                changes_by_sev[ch.severity].append(ch)
            else:
                changes_by_sev[SEVERITY_INFO].append(ch)

        attachments: list[dict[str, Any]] = []
        for sev in severity_order:
            sev_changes = changes_by_sev[sev]
            if not sev_changes:
                continue

            color = SLACK_COLOR_MAP.get(sev, SLACK_COLOR_DEFAULT)
            fields: list[dict[str, Any]] = []
            for ch in sev_changes:
                desc = ch.detail or (f"`{ch.was}` -> `{ch.now}`" if ch.was or ch.now else ch.kind)
                fields.append(
                    {
                        "title": f"`{ch.field}`",
                        "value": f"*{ch.kind}*: {desc}",
                        "short": len(ch.field) <= 24,
                    }
                )

            count_str = f" ({len(sev_changes)})" if len(sev_changes) > 1 else ""
            attachments.append(
                {
                    "color": color,
                    "title": f"[{sev.upper()}]{count_str}",
                    "fields": fields,
                    "ts": int(event.detected_at),
                }
            )

        payload: dict[str, Any] = {
            "text": header_text,
            "attachments": attachments,
        }
        if self._channel:
            payload["channel"] = self._channel
        return payload

    def send(self, event: DriftEvent | Change) -> bool:
        """Send formatted Slack message with retries.

        Returns True if successful, False otherwise. Never raises exceptions.
        """
        # Normalize Change to DriftEvent if passed directly
        if isinstance(event, Change):
            drift_event = DriftEvent(
                vendor="unknown",
                endpoint="unknown",
                changes=(event,),
            )
        else:
            drift_event = event

        payload = self._build_payload(drift_event)
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "schemawatch-slack-alert/0.1.0",
        }

        for attempt in range(1, self._max_retries + 2):
            try:
                req = urllib.request.Request(
                    self._url,
                    data=data,
                    headers=headers,
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    if 200 <= resp.status < 300:
                        return True
            except Exception as exc:
                should_retry, retry_after = should_retry_error(exc)
                # Privacy rule: NEVER log the webhook URL
                logger.warning(
                    "schemawatch: slack alert delivery failed (attempt %d/%d): %s",
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
            "schemawatch: slack alert delivery exhausted all retries for %s %s",
            drift_event.vendor,
            drift_event.endpoint,
        )
        return False
