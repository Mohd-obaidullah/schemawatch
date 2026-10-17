from __future__ import annotations

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
async def test_get_stats(seeded_client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await seeded_client.get("/api/stats", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["total_endpoints"] == 4
    # 3 active (unacknowledged): 1 breaking (stripe), 1 warning (twilio), 1 info (sendgrid)
    assert data["active_alerts_count"] == 3
    assert data["breaking_alerts_count"] == 1
    assert data["warning_alerts_count"] == 1
    assert data["info_alerts_count"] == 1

    # Exactly 12 hourly buckets
    assert len(data["alerts_per_hour"]) == 12
    for bucket in data["alerts_per_hour"]:
        assert "hour" in bucket
        assert "count" in bucket
        assert "breaking" in bucket
        assert "warning" in bucket
        assert "info" in bucket


@pytest.mark.asyncio
async def test_get_config_privacy(client: httpx.AsyncClient, auth_headers: dict[str, str]) -> None:
    resp = await client.get("/api/config", headers=auth_headers)
    assert resp.status_code == 200
    cfg = resp.json()

    assert cfg["slack_configured"] is True
    assert cfg["webhook_configured"] is True
    assert cfg["dev_mode"] is False
    assert cfg["min_alert_severity"] == "info"
    assert cfg["learn_samples"] == 2
    assert cfg["database_type"] == "sqlite"

    # Strict Privacy Rule: Tokens and raw webhook URLs must NEVER be present in /api/config
    cfg_text = resp.text
    assert "https://" not in cfg_text
    assert "http://" not in cfg_text
    assert "secret" not in cfg_text.lower()
    assert "token" not in cfg_text.lower()
