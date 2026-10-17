from __future__ import annotations

import asyncio
import json
from collections.abc import MutableMapping
from typing import Any

import httpx
import pytest
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_sse_stream_receives_drift_events_on_ingest(
    app: FastAPI, client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    vendor = "stripe"
    endpoint = "POST /v1/charges"

    # Learn baseline first (2 samples)
    await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": {"charge_id": 100}},
        headers=auth_headers,
    )
    await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": {"charge_id": 200}},
        headers=auth_headers,
    )

    received_lines: list[str] = []
    received_status: list[int] = []
    received_headers: dict[str, str] = {}
    stream_done = asyncio.Event()

    async def run_sse_listener() -> None:
        scope: dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "path": "/api/events/stream",
            "headers": [(b"authorization", auth_headers["Authorization"].encode("utf-8"))],
            "query_string": b"",
        }

        async def receive() -> dict[str, str]:
            await stream_done.wait()
            return {"type": "http.disconnect"}

        async def send(msg: MutableMapping[str, Any]) -> None:
            if msg["type"] == "http.response.start":
                status = msg.get("status")
                if status is not None:
                    received_status.append(int(status))
                raw_hdrs = msg.get("headers", [])
                if isinstance(raw_hdrs, list):
                    for k, v in raw_hdrs:
                        received_headers[k.decode("latin1")] = v.decode("latin1")
            elif msg["type"] == "http.response.body":
                body = msg.get("body", b"")
                if isinstance(body, bytes):
                    text = body.decode("utf-8")
                    for line in text.splitlines():
                        if line:
                            received_lines.append(line)
                    if any("event: drift" in item for item in received_lines) and any(
                        "data:" in item for item in received_lines
                    ):
                        stream_done.set()

        await app(scope, receive, send)

    sse_task = asyncio.create_task(run_sse_listener())
    await asyncio.sleep(0.05)

    # Ingest a drifting payload
    drift_payload = {"charge_id": "ch_string_id"}
    resp = await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": drift_payload},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    # Wait for SSE listener to receive the event
    await asyncio.wait_for(stream_done.wait(), timeout=3.0)
    await sse_task

    # Verify status and headers
    assert received_status == [200]
    assert "text/event-stream" in received_headers.get("content-type", "")

    # Verify event structure
    assert any("event: drift" in line for line in received_lines)
    data_lines = [item for item in received_lines if item.startswith("data:")]
    assert len(data_lines) > 0

    event_payload = json.loads(data_lines[0].replace("data:", "").strip())
    assert event_payload["vendor"] == "stripe"
    assert event_payload["endpoint"] == "POST /v1/charges"
    assert event_payload["highest_severity"] == "breaking"
    assert len(event_payload["changes"]) == 1
    assert event_payload["changes"][0]["field"] == "$.charge_id"
    assert event_payload["changes"][0]["kind"] == "type_changed"
