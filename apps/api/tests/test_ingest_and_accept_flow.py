from __future__ import annotations

import httpx
import pytest


@pytest.mark.asyncio
async def test_ingest_and_accept_flow_end_to_end(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    vendor = "payco"
    endpoint = "POST /v1/charges"

    # Step 1: Learning phase (learn_samples = 2)
    sample_1 = {"user_id": 1001, "amount": 50, "currency": "USD"}
    sample_2 = {"user_id": 1002, "amount": 75, "currency": "USD"}

    resp1 = await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": sample_1},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    assert resp1.json()["changes_detected"] == 0

    resp2 = await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": sample_2},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    assert resp2.json()["changes_detected"] == 0

    # Verify baseline established
    ep_list_resp = await client.get("/api/endpoints", headers=auth_headers)
    assert ep_list_resp.status_code == 200
    endpoints = ep_list_resp.json()["items"]
    assert len(endpoints) == 1
    ep_id = endpoints[0]["id"]
    assert endpoints[0]["current_baseline_version"] == 1
    assert endpoints[0]["status"] == "healthy"

    # Step 2: Conforming sample post-learning
    conforming_sample = {"user_id": 1003, "amount": 100, "currency": "USD"}
    resp_conf = await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": conforming_sample},
        headers=auth_headers,
    )
    assert resp_conf.status_code == 200
    assert resp_conf.json()["changes_detected"] == 0

    # Step 3: Drift sample (amount: integer -> string)
    drift_sample = {"user_id": 1004, "amount": "100.00_USD", "currency": "USD"}
    resp_drift = await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": drift_sample},
        headers=auth_headers,
    )
    assert resp_drift.status_code == 200
    drift_res = resp_drift.json()
    assert drift_res["changes_detected"] == 1
    assert len(drift_res["event_ids"]) == 1

    # Verify endpoint is now broken and has open alert
    ep_resp = await client.get(f"/api/endpoints/{ep_id}", headers=auth_headers)
    assert ep_resp.status_code == 200
    assert ep_resp.json()["status"] == "broken"
    assert ep_resp.json()["open_alerts_count"] == 1

    # Verify event persisted with observed_schema_json and alert_deliveries
    events_resp = await client.get(
        f"/api/events?endpoint_id={ep_id}&acknowledged=false",
        headers=auth_headers,
    )
    assert events_resp.status_code == 200
    event_item = events_resp.json()["items"][0]
    assert event_item["field_path"] == "$.amount"
    assert event_item["kind"] == "type_changed"
    assert event_item["severity"] == "breaking"
    assert event_item["observed_schema"] is not None

    # Step 4: Accept new schema baseline
    accept_resp = await client.post(
        f"/api/endpoints/{ep_id}/accept",
        headers=auth_headers,
    )
    assert accept_resp.status_code == 200
    acc_data = accept_resp.json()
    assert acc_data["new_baseline_version"] == 2
    assert acc_data["events_acknowledged"] == 1

    # Verify endpoint status returned to healthy and baseline is version 2
    ep_after = await client.get(f"/api/endpoints/{ep_id}", headers=auth_headers)
    assert ep_after.json()["current_baseline_version"] == 2
    assert ep_after.json()["status"] == "healthy"
    assert ep_after.json()["open_alerts_count"] == 0

    # Verify baseline v2 now permits string for amount
    base_v2 = await client.get(f"/api/endpoints/{ep_id}/baseline?version=2", headers=auth_headers)
    assert base_v2.status_code == 200
    schema_v2 = base_v2.json()["schema"]
    assert "string" in schema_v2["properties"]["amount"]["types"]


@pytest.mark.asyncio
async def test_ingest_payload_size_limit_returns_413(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    # Huge payload exceeding 1MB limit
    huge_str = "x" * 1_200_000
    resp = await client.post(
        "/api/ingest",
        json={"vendor": "big", "endpoint": "/huge", "payload": {"data": huge_str}},
        headers=auth_headers,
    )
    assert resp.status_code == 413
    assert "exceeds limit" in resp.json()["detail"].lower()
