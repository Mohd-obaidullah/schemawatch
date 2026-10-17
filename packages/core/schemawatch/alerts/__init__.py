from __future__ import annotations

import logging
from collections.abc import Callable

from schemawatch.alerts.slack import SlackAlert
from schemawatch.alerts.webhook import WebhookAlert
from schemawatch.diff import Change, DriftEvent

logger = logging.getLogger(__name__)


def fan_out(
    *dispatchers: Callable[[DriftEvent], None],
) -> Callable[[DriftEvent | Change], None]:
    """Combine multiple alert dispatchers into a single fail-open callback.

    Dispatches sequentially to each handler. If one handler raises an exception,
    the exception is logged and swallowed so subsequent handlers still execute.
    """

    def _composite(event: DriftEvent | Change) -> None:
        drift_event = (
            event
            if isinstance(event, DriftEvent)
            else DriftEvent(vendor="unknown", endpoint="unknown", changes=(event,))
        )
        for dispatcher in dispatchers:
            try:
                dispatcher(drift_event)
            except Exception as exc:
                logger.exception("schemawatch fan_out: dispatcher failed: %s", exc)

    return _composite


__all__ = [
    "SlackAlert",
    "WebhookAlert",
    "fan_out",
]
