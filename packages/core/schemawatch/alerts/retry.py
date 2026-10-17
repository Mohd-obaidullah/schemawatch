from __future__ import annotations

import logging
import urllib.error
from typing import Final

logger = logging.getLogger(__name__)

RETRYABLE_STATUS_CODES: Final[frozenset[int]] = frozenset({408, 425, 429})
MAX_RETRY_AFTER_SECONDS: Final[float] = 30.0


def should_retry_error(exc: Exception) -> tuple[bool, float | None]:
    """Determine whether an HTTP/network exception should be retried.

    Rules:
    - Network errors (URLError, OSError, TimeoutError) are retried.
    - HTTP status codes 408, 425, 429, and 5xx are retried.
    - Other 4xx status codes (400, 401, 403, 404, etc.) are NOT retried.
    - If a Retry-After header is present on a retryable HTTP response, its value
      is honoured as seconds and capped at 30 seconds.

    Returns:
        (should_retry, retry_after_delay_in_seconds)
    """
    if isinstance(exc, urllib.error.HTTPError):
        code = exc.code
        if code in RETRYABLE_STATUS_CODES or code >= 500:
            retry_after: float | None = None
            if exc.headers:
                raw_ra = exc.headers.get("Retry-After")
                if raw_ra:
                    try:
                        retry_after = min(max(0.0, float(raw_ra)), MAX_RETRY_AFTER_SECONDS)
                    except ValueError:
                        retry_after = None
            return True, retry_after
        # Other 4xx are client errors and should NOT be retried
        if 400 <= code < 500:
            return False, None
        return False, None

    if isinstance(exc, (urllib.error.URLError, OSError, TimeoutError)):
        return True, None

    return False, None
