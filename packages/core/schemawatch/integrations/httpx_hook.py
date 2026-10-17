from __future__ import annotations

import logging
import queue
import re
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import httpx

from schemawatch.redact import DEFAULT_MAX_PAYLOAD_BYTES
from schemawatch.watchdog import Watchdog

logger = logging.getLogger(__name__)

_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_LONG_HEX_RE = re.compile(r"^[0-9a-fA-F]{16,}$")


def normalize_endpoint(method: str, path: str) -> str:
    """Normalize an HTTP endpoint URL path and include the HTTP method in the key.

    Replaces numeric, UUID, and long-hex segments with '{id}'.
    Example: GET /v1/users/42 -> GET /v1/users/{id}
    """
    segments = path.split("/")
    norm: list[str] = []
    for seg in segments:
        if not seg:
            norm.append(seg)
            continue
        if seg.isdigit() or _UUID_RE.match(seg) or _LONG_HEX_RE.match(seg):
            norm.append("{id}")
        else:
            norm.append(seg)
    norm_path = "/".join(norm) or "/"
    return f"{method.upper()} {norm_path}"


def _default_endpoint_extractor(request: httpx.Request) -> str:
    """Extract normalized method and path as the endpoint identifier."""
    return normalize_endpoint(request.method, request.url.path or "/")


def _default_vendor_extractor(request: httpx.Request) -> str:
    """Extract host as the vendor identifier."""
    return request.url.host or "unknown_vendor"


class SchemawatchHTTPXHook:
    """Fail-open, non-blocking HTTPX event hook with a bounded queue.

    Attaches to httpx.Client or httpx.AsyncClient via event_hooks={'response': [hook]}.
    Copies response bodies into a bounded in-process queue and processes them
    off the request hot path so production requests are never delayed.
    """

    def __init__(
        self,
        watchdog: Watchdog,
        vendor: str | Callable[[httpx.Request], str] | None = None,
        endpoint: str | Callable[[httpx.Request], str] | None = None,
        max_queue_size: int = 1000,
        max_body_bytes: int | None = None,
    ) -> None:
        self.watchdog = watchdog
        self._vendor = vendor
        self._endpoint = endpoint
        self._max_queue_size = max_queue_size
        raw_max = getattr(watchdog, "max_payload_bytes", DEFAULT_MAX_PAYLOAD_BYTES)
        self._max_body_bytes = (
            max_body_bytes
            if max_body_bytes is not None
            else (raw_max if isinstance(raw_max, int) else DEFAULT_MAX_PAYLOAD_BYTES)
        )
        self._dropped_samples = 0
        self._lock = threading.Lock()

        self._queue: queue.Queue[tuple[str, str, bytes] | None] = queue.Queue(
            maxsize=max_queue_size
        )
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="schemawatch-httpx-worker",
            daemon=True,
        )
        self._running = True
        self._worker_thread.start()

    @property
    def dropped_samples(self) -> int:
        """Count of samples dropped due to bounded queue pressure."""
        with self._lock:
            return self._dropped_samples

    def __call__(self, response: httpx.Response) -> None:
        """Sync response hook handler."""
        self.on_response(response)

    def on_response(self, response: httpx.Response) -> None:
        """Handle response synchronously without blocking."""
        try:
            self._enqueue_response(response)
        except Exception as exc:
            # Hard rule: Fail open, never affect the host application
            logger.exception("schemawatch httpx hook: failed in on_response: %s", exc)

    async def on_async_response(self, response: httpx.Response) -> None:
        """Handle response asynchronously without blocking."""
        try:
            self._enqueue_response(response)
        except Exception as exc:
            # Hard rule: Fail open, never affect the host application
            logger.exception("schemawatch httpx hook: failed in on_async_response: %s", exc)

    def _resolve_vendor(self, request: httpx.Request) -> str:
        if callable(self._vendor):
            return str(self._vendor(request))
        if isinstance(self._vendor, str):
            return self._vendor
        return _default_vendor_extractor(request)

    def _resolve_endpoint(self, request: httpx.Request) -> str:
        if callable(self._endpoint):
            return str(self._endpoint(request))
        if isinstance(self._endpoint, str):
            return self._endpoint
        return _default_endpoint_extractor(request)

    def _enqueue_response(self, response: httpx.Response) -> None:
        """Non-blocking put into bounded queue."""
        request = response.request
        if request is None:
            return

        # Rule: Inspect only 2xx responses
        if not (200 <= response.status_code < 300):
            return

        # Fast header check for payload size limit
        cl = response.headers.get("content-length")
        if cl:
            try:
                if int(cl) > self._max_body_bytes:
                    return
            except ValueError:
                pass

        # Read content (httpx response.read() caches bytes in response._content)
        content: bytes = response.read()
        if not content:
            return

        # Rule: Skip bodies > max_body_bytes
        if len(content) > self._max_body_bytes:
            return

        # Rule: Inspect only JSON responses
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type and not (
            content.strip().startswith(b"{") or content.strip().startswith(b"[")
        ):
            return

        vendor_name = self._resolve_vendor(request)
        endpoint_name = self._resolve_endpoint(request)

        try:
            self._queue.put_nowait((vendor_name, endpoint_name, content))
        except queue.Full:
            with self._lock:
                self._dropped_samples += 1
            logger.warning(
                "schemawatch: queue full (dropped sample for %s %s, total dropped: %d)",
                vendor_name,
                endpoint_name,
                self._dropped_samples,
            )

    def _process_queue(self) -> None:
        """Background worker thread draining the queue."""
        while self._running:
            try:
                item = self._queue.get(timeout=0.2)
            except queue.Empty:
                continue

            if item is None:
                self._queue.task_done()
                break

            vendor, endpoint, raw_bytes = item
            try:
                self.watchdog.observe(vendor, endpoint, raw_bytes)
            except Exception as exc:
                logger.exception("schemawatch worker: error observing: %s", exc)
            finally:
                self._queue.task_done()

    def flush(self, timeout: float = 3.0) -> None:
        """Wait for currently queued items to be processed."""
        try:
            self._queue.join()
        except Exception:
            pass

    def close(self, timeout: float = 3.0) -> None:
        """Stop background worker thread."""
        self._running = False
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass
        self._worker_thread.join(timeout=timeout)


def create_httpx_hook(
    watchdog: Watchdog,
    vendor: str | Callable[[Any], str] | None = None,
    endpoint: str | Callable[[Any], str] | None = None,
    max_queue_size: int = 1000,
    max_body_bytes: int | None = None,
) -> SchemawatchHTTPXHook:
    """Factory creating a SchemawatchHTTPXHook instance."""
    return SchemawatchHTTPXHook(
        watchdog=watchdog,
        vendor=vendor,
        endpoint=endpoint,
        max_queue_size=max_queue_size,
        max_body_bytes=max_body_bytes,
    )
