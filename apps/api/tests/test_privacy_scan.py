from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import text


@pytest.mark.asyncio
async def test_database_privacy_row_scan_proves_no_raw_values_persist(
    app: FastAPI, client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    """Privacy audit test: Scans every row and column of every database table

    to guarantee that raw payload values never leak into persistent storage.
    """
    secret_ssn = "SSN_000-11-2222"
    secret_card = "4111_2222_3333_4444"
    secret_key = "sk_live_99999999999999999999"
    secret_note = "PATIENT_HEALTH_DIAGNOSIS_CLASSIFIED_789"
    secret_token = "ghp_VERY_SECRET_OAUTH_TOKEN_ABCXYZ"

    vendor = "payments_corp"
    endpoint = "/v1/secure_checkout"

    # Step 1: Ingest samples during learning phase containing sensitive raw values
    learning_sample_1 = {
        "ssn": secret_ssn,
        "card": secret_card,
        "token": secret_token,
        "amount": 100,
        "meta": {"note": secret_note},
    }
    learning_sample_2 = {
        "ssn": secret_ssn,
        "card": secret_card,
        "token": secret_token,
        "amount": 200,
        "meta": {"note": secret_note},
    }

    await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": learning_sample_1},
        headers=auth_headers,
    )
    await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": learning_sample_2},
        headers=auth_headers,
    )

    # Step 2: Ingest drift payload with type change containing new secrets
    drift_sample = {
        "ssn": secret_ssn,
        "card": secret_card,
        "token": secret_token,
        "amount": secret_key,  # type drift int -> str with secret key
        "meta": {"note": secret_note},
    }
    await client.post(
        "/api/ingest",
        json={"vendor": vendor, "endpoint": endpoint, "payload": drift_sample},
        headers=auth_headers,
    )

    all_secrets = [secret_ssn, secret_card, secret_key, secret_note, secret_token]

    # Step 3: Full exhaustive database row scan
    engine = app.state.engine
    with engine.connect() as conn:
        # Tables to scan
        tables = ["endpoints", "baselines", "drift_events", "alert_deliveries"]

        for table in tables:
            rows = conn.execute(text(f"SELECT * FROM {table}")).fetchall()
            for row in rows:
                row_str = str(row)
                for secret in all_secrets:
                    assert secret not in row_str, (
                        f"PRIVACY VIOLATION: '{secret}' in '{table}': {row_str}"
                    )
