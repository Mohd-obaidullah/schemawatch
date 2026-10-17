from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from schemawatch_api.scripts.seed_demo import seed_demo_data


@pytest.fixture
def seeded_app(app: FastAPI) -> FastAPI:
    session_factory = app.state.service.session_factory
    with session_factory() as session:
        seed_demo_data(session, learn_samples=2)
    return app


@pytest.fixture
async def seeded_client(seeded_app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=seeded_app),
        base_url="http://testserver",
    )


@pytest.mark.asyncio
async def test_list_events_unfiltered(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await seeded_client.get("/api/events", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 4
    assert data["total"] == 4


@pytest.mark.asyncio
async def test_list_events_filter_severity(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Filter breaking
    resp = await seeded_client.get("/api/events?severity=breaking", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert all(e["severity"] == "breaking" for e in data["items"])
    assert len(data["items"]) == 2  # Stripe (unack) + GitHub (ack)

    # Filter warning
    resp_warn = await seeded_client.get("/api/events?severity=warning", headers=auth_headers)
    assert resp_warn.status_code == 200
    assert len(resp_warn.json()["items"]) == 1

    # Filter info
    resp_info = await seeded_client.get("/api/events?severity=info", headers=auth_headers)
    assert resp_info.status_code == 200
    assert len(resp_info.json()["items"]) == 1


@pytest.mark.asyncio
async def test_list_events_filter_vendor_and_acknowledged(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Filter vendor=stripe
    resp = await seeded_client.get("/api/events?vendor=stripe", headers=auth_headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0]["vendor"] == "stripe"

    # Filter acknowledged=false
    resp_unack = await seeded_client.get("/api/events?acknowledged=false", headers=auth_headers)
    assert resp_unack.status_code == 200
    assert len(resp_unack.json()["items"]) == 3

    # Filter acknowledged=true
    resp_ack = await seeded_client.get("/api/events?acknowledged=true", headers=auth_headers)
    assert resp_ack.status_code == 200
    assert len(resp_ack.json()["items"]) == 1
    assert resp_ack.json()["items"][0]["vendor"] == "github"


@pytest.mark.asyncio
async def test_list_events_filter_since(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    since_ts = (datetime.now(timezone.utc) - timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = await seeded_client.get(f"/api/events?since={since_ts}", headers=auth_headers)
    assert resp.status_code == 200
    # Stripe, Twilio, SendGrid were within last 6 hours; GitHub was 1 day ago
    assert len(resp.json()["items"]) == 3


@pytest.mark.asyncio
async def test_acknowledge_and_unacknowledge_event(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Get unacknowledged event (e.g. Stripe)
    list_resp = await seeded_client.get("/api/events?acknowledged=false", headers=auth_headers)
    event_id = list_resp.json()["items"][0]["id"]

    # 1. Acknowledge
    ack_resp = await seeded_client.post(f"/api/events/{event_id}/ack", headers=auth_headers)
    assert ack_resp.status_code == 200
    assert ack_resp.json()["acknowledged"] is True

    # Verify event is now acknowledged
    verify_resp = await seeded_client.get("/api/events?acknowledged=true", headers=auth_headers)
    ack_ids = {e["id"] for e in verify_resp.json()["items"]}
    assert event_id in ack_ids

    # 2. Unacknowledge
    unack_resp = await seeded_client.post(f"/api/events/{event_id}/unack", headers=auth_headers)
    assert unack_resp.status_code == 200
    assert unack_resp.json()["acknowledged"] is False


@pytest.mark.asyncio
async def test_acknowledge_event_not_found(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.post("/api/events/99999/ack", headers=auth_headers)
    assert resp.status_code == 404
