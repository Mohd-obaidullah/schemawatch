from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest
from schemawatch.diff import DriftEvent
from schemawatch.integrations.httpx_hook import (
    SchemawatchHTTPXHook,
    create_httpx_hook,
    normalize_endpoint,
)
from schemawatch.watchdog import Watchdog


def test_httpx_sync_client_integration() -> None:
    alerts: list[DriftEvent] = []
    watchdog = Watchdog(learning_threshold=2, on_alert=alerts.append)
    hook = create_httpx_hook(watchdog=watchdog, vendor="stripe", endpoint="/v1/charges")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=json.dumps({"charge_id": 123}).encode("utf-8"),
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler), event_hooks={"response": [hook]})
    try:
        # 2 learning requests
        client.get("https://api.stripe.com/v1/charges")
        client.get("https://api.stripe.com/v1/charges")
        hook.flush()
        assert len(alerts) == 0

        # Drift request
        def drift_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=200,
                headers={"content-type": "application/json"},
                content=json.dumps({"charge_id": "ch_123"}).encode("utf-8"),
                request=request,
            )

        client_drift = httpx.Client(
            transport=httpx.MockTransport(drift_handler),
            event_hooks={"response": [hook]},
        )
        client_drift.get("https://api.stripe.com/v1/charges")
        hook.flush()

        assert len(alerts) == 1
        assert alerts[0].vendor == "stripe"
        assert alerts[0].endpoint == "/v1/charges"
        assert alerts[0].changes[0].field == "$.charge_id"
        assert alerts[0].changes[0].kind == "type_changed"
    finally:
        hook.close()


@pytest.mark.asyncio
async def test_httpx_async_client_integration() -> None:
    alerts: list[DriftEvent] = []
    watchdog = Watchdog(learning_threshold=1, on_alert=alerts.append)
    hook = create_httpx_hook(watchdog=watchdog, vendor="github", endpoint="/user")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"login": "octocat"}',
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        event_hooks={"response": [hook.on_async_response]},
    ) as client:
        # Learn
        await client.get("https://api.github.com/user")
        hook.flush()
        assert len(alerts) == 0

    # Drift
    def drift_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"login": 9999}',
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(drift_handler),
        event_hooks={"response": [hook.on_async_response]},
    ) as client:
        await client.get("https://api.github.com/user")
        hook.flush()

    hook.close()
    assert len(alerts) == 1
    assert alerts[0].changes[0].kind == "type_changed"


def test_httpx_endpoint_normalization() -> None:
    # 1. Numeric segment normalization
    assert normalize_endpoint("GET", "/v1/users/42/tokens/100") == "GET /v1/users/{id}/tokens/{id}"

    # 2. UUID segment normalization
    assert (
        normalize_endpoint("POST", "/orders/123e4567-e89b-12d3-a456-426614174000/items")
        == "POST /orders/{id}/items"
    )

    # 3. Long hex segment normalization
    assert normalize_endpoint("DELETE", "/tokens/abcdef0123456789abcdef") == "DELETE /tokens/{id}"

    # 4. Preserves static endpoints and prepends HTTP method
    assert normalize_endpoint("PUT", "/api/v2/products") == "PUT /api/v2/products"

    # 5. Verify default extractor integration with hook
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    req = httpx.Request(
        "POST",
        "https://api.stripe.com/v1/customers/999/charges/550e8400-e29b-41d4-a716-446655440000",
    )
    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"id": "ch_1"}',
        request=req,
    )
    hook(resp)
    hook.flush()
    hook.close()

    watchdog.observe.assert_called_once_with(
        "api.stripe.com",
        "POST /v1/customers/{id}/charges/{id}",
        b'{"id": "ch_1"}',
    )


def test_httpx_hook_skips_non_2xx_responses() -> None:
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    req = httpx.Request("GET", "https://api.test.com/v1/errors")

    # 400 Bad Request
    resp_400 = httpx.Response(
        status_code=400,
        headers={"content-type": "application/json"},
        content=b'{"error": "bad request"}',
        request=req,
    )
    # 404 Not Found
    resp_404 = httpx.Response(
        status_code=404,
        headers={"content-type": "application/json"},
        content=b'{"error": "not found"}',
        request=req,
    )
    # 500 Internal Server Error
    resp_500 = httpx.Response(
        status_code=500,
        headers={"content-type": "application/json"},
        content=b'{"error": "server error"}',
        request=req,
    )

    hook(resp_400)
    hook(resp_404)
    hook(resp_500)
    hook.flush()
    hook.close()

    # None of the non-2xx responses should be observed
    watchdog.observe.assert_not_called()


def test_httpx_hook_skips_bodies_exceeding_max_body_bytes() -> None:
    watchdog = MagicMock()
    # Limit body size to 50 bytes
    hook = create_httpx_hook(watchdog=watchdog, max_body_bytes=50)

    req = httpx.Request("GET", "https://api.test.com/large")

    # 1. Body exceeds max_body_bytes
    large_body = b'{"data": "' + (b"x" * 60) + b'"}'
    resp_large = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=large_body,
        request=req,
    )
    hook(resp_large)

    # 2. Content-Length header claims oversized body
    resp_cl_large = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json", "content-length": "200"},
        content=b'{"data": "small"}',
        request=req,
    )
    hook(resp_cl_large)

    # 3. Conforming small body should be observed
    small_body = b'{"data": "ok"}'
    resp_small = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=small_body,
        request=req,
    )
    hook(resp_small)

    hook.flush()
    hook.close()

    # Only the small body should be observed
    watchdog.observe.assert_called_once_with(
        "api.test.com",
        "GET /large",
        small_body,
    )


def test_httpx_hook_dynamic_extractors() -> None:
    watchdog = MagicMock()
    hook = SchemawatchHTTPXHook(
        watchdog=watchdog,
        vendor=lambda req: req.headers.get("x-vendor", "default_v"),
        endpoint=lambda req: f"/custom{req.url.path}",
    )

    req = httpx.Request("GET", "https://api.test.com/items", headers={"x-vendor": "vendor_a"})
    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"ok": true}',
        request=req,
    )
    hook(resp)
    hook.flush()
    hook.close()

    watchdog.observe.assert_called_once_with("vendor_a", "/custom/items", b'{"ok": true}')


def test_httpx_hook_bounded_queue_drops_samples_under_pressure() -> None:
    watchdog = MagicMock()
    hook = SchemawatchHTTPXHook(watchdog=watchdog, max_queue_size=2)
    # Pause worker thread
    hook._running = False
    hook._queue.put(None)  # exit worker
    hook._worker_thread.join(timeout=1.0)

    # Fill queue to capacity (2 items)
    req = httpx.Request("GET", "https://api.test.com/v1")
    resp = httpx.Response(status_code=200, content=b'{"x": 1}', request=req)

    # Item 1 and 2 succeed
    hook(resp)
    hook(resp)
    assert hook.dropped_samples == 0

    # Item 3 must be dropped without raising or blocking
    hook(resp)
    assert hook.dropped_samples == 1


def test_httpx_hook_fail_open_on_error() -> None:
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    bad_resp = MagicMock()
    bad_resp.read.side_effect = OSError("Socket read failure")

    # Hook must not raise
    hook(bad_resp)
    hook.close()


def test_httpx_hook_skips_non_json_responses() -> None:
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    req = httpx.Request("GET", "https://example.com/index.html")
    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "text/html"},
        content=b"<html>Hello</html>",
        request=req,
    )
    hook(resp)
    hook.flush()
    hook.close()

    watchdog.observe.assert_not_called()


@pytest.mark.asyncio
async def test_httpx_async_hook_fail_open_on_error() -> None:
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    bad_resp = MagicMock()
    bad_resp.read.side_effect = RuntimeError("Async read failed")

    # Must not raise
    await hook.on_async_response(bad_resp)
    hook.close()


def test_httpx_hook_empty_response_or_missing_request() -> None:
    watchdog = MagicMock()
    hook = create_httpx_hook(watchdog=watchdog)

    # Empty content
    req = httpx.Request("GET", "https://example.com/empty")
    resp = httpx.Response(status_code=204, content=b"", request=req)
    hook(resp)

    # Missing request
    resp_no_req = httpx.Response(status_code=200, content=b'{"ok": true}')
    resp_no_req._request = None
    hook(resp_no_req)

    hook.flush()
    hook.close()
    watchdog.observe.assert_not_called()


def test_httpx_hook_worker_exception_swallowed() -> None:
    watchdog = MagicMock()
    watchdog.observe.side_effect = RuntimeError("Observe threw exception")

    hook = create_httpx_hook(watchdog=watchdog)
    req = httpx.Request("GET", "https://example.com/api")
    resp = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        content=b'{"data": 1}',
        request=req,
    )

    hook(resp)
    hook.flush()
    hook.close()
    watchdog.observe.assert_called_once()
