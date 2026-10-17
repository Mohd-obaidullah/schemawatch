from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from schemawatch_api.app import create_app
from schemawatch_api.config import Settings

TEST_API_TOKEN = "test-secret-token-12345"


@pytest.mark.asyncio
async def test_restart_persistence_retains_baselines_and_events(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "persistence_test.db"
    db_url = f"sqlite:///{db_file.as_posix()}"

    settings_1 = Settings(
        database_url=db_url,
        api_token=TEST_API_TOKEN,
        dev_mode=False,
        learn_samples=2,
    )
    auth_headers = {"Authorization": f"Bearer {TEST_API_TOKEN}"}

    # Instance 1: Learn baseline and create an event
    app_1 = create_app(settings_1)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_1),
        base_url="http://testserver",
    ) as client_1:
        # Learn
        await client_1.post(
            "/api/ingest",
            json={
                "vendor": "twilio",
                "endpoint": "/messages",
                "payload": {"id": 1, "status": "sent"},
            },
            headers=auth_headers,
        )
        await client_1.post(
            "/api/ingest",
            json={
                "vendor": "twilio",
                "endpoint": "/messages",
                "payload": {"id": 2, "status": "sent"},
            },
            headers=auth_headers,
        )
        # Drift
        await client_1.post(
            "/api/ingest",
            json={
                "vendor": "twilio",
                "endpoint": "/messages",
                "payload": {"id": "str_id", "status": "sent"},
            },
            headers=auth_headers,
        )

    # Dispose instance 1 engine
    app_1.state.engine.dispose()

    # Instance 2: Start new app instance pointing to the same SQLite DB file
    settings_2 = Settings(
        database_url=db_url,
        api_token=TEST_API_TOKEN,
        dev_mode=False,
        learn_samples=2,
    )
    app_2 = create_app(settings_2)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app_2),
        base_url="http://testserver",
    ) as client_2:
        # Verify endpoint and baseline survived restart
        ep_resp = await client_2.get("/api/endpoints", headers=auth_headers)
        assert ep_resp.status_code == 200
        items = ep_resp.json()["items"]
        assert len(items) == 1
        ep = items[0]
        assert ep["vendor"] == "twilio"
        assert ep["current_baseline_version"] == 1
        assert ep["status"] == "broken"
        assert ep["open_alerts_count"] == 1

        # Verify drift event survived restart
        events_resp = await client_2.get(
            f"/api/events?endpoint_id={ep['id']}", headers=auth_headers
        )
        assert events_resp.status_code == 200
        evts = events_resp.json()["items"]
        assert len(evts) == 1
        assert evts[0]["field_path"] == "$.id"
        assert evts[0]["kind"] == "type_changed"

    app_2.state.engine.dispose()
