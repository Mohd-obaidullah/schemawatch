from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from schemawatch_api.scripts.seed_demo import seed_demo_data


@pytest.fixture
def seeded_app(app: FastAPI) -> FastAPI:
    """Fixture that seeds demo data into the app's in-memory database."""
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
async def test_list_endpoints_empty(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["next_cursor"] is None
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_endpoints_seeded(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await seeded_client.get("/api/endpoints", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 4
    assert data["total"] == 4

    vendors = {ep["vendor"] for ep in data["items"]}
    assert "stripe" in vendors
    assert "twilio" in vendors
    assert "sendgrid" in vendors
    assert "github" in vendors

    # Check status values
    status_map = {ep["vendor"]: ep["status"] for ep in data["items"]}
    assert status_map["stripe"] == "broken"
    assert status_map["twilio"] == "warning"
    assert status_map["sendgrid"] == "healthy"
    assert status_map["github"] == "healthy"


@pytest.mark.asyncio
async def test_list_endpoints_pagination(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Page 1 with limit=2
    resp1 = await seeded_client.get("/api/endpoints?limit=2", headers=auth_headers)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert len(data1["items"]) == 2
    assert data1["next_cursor"] is not None

    # Page 2 using cursor
    cursor = data1["next_cursor"]
    resp2 = await seeded_client.get(f"/api/endpoints?limit=2&cursor={cursor}", headers=auth_headers)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert len(data2["items"]) == 2


@pytest.mark.asyncio
async def test_get_endpoint_by_id(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Fetch list first to get a valid ID
    list_resp = await seeded_client.get("/api/endpoints", headers=auth_headers)
    ep_id = list_resp.json()["items"][0]["id"]

    resp = await seeded_client.get(f"/api/endpoints/{ep_id}", headers=auth_headers)
    assert resp.status_code == 200
    ep = resp.json()
    assert ep["id"] == ep_id
    assert "vendor" in ep
    assert "endpoint" in ep
    assert "status" in ep


@pytest.mark.asyncio
async def test_get_endpoint_not_found(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/endpoints/99999", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_endpoint_baseline(
    seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    list_resp = await seeded_client.get("/api/endpoints", headers=auth_headers)
    ep_id = list_resp.json()["items"][0]["id"]

    resp = await seeded_client.get(f"/api/endpoints/{ep_id}/baseline", headers=auth_headers)
    assert resp.status_code == 200
    b = resp.json()
    assert b["endpoint_id"] == ep_id
    assert b["version"] == 1
    assert "properties" in b["schema"] or "types" in b["schema"]


@pytest.mark.asyncio
async def test_get_endpoint_baseline_not_found(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/endpoints/99999/baseline", headers=auth_headers)
    assert resp.status_code == 404
