from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from schemawatch_api.app import create_app
from schemawatch_api.config import Settings

TEST_API_TOKEN = "test-secret-token-12345"


def test_startup_refused_without_token() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        api_token="",
        dev_mode=False,
    )
    with pytest.raises(ValueError, match="SCHEMAWATCH_API_TOKEN is required"):
        create_app(settings)


def test_startup_refused_with_placeholder_token() -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        api_token="your-random-secure-token-here",
        dev_mode=False,
    )
    with pytest.raises(ValueError, match="placeholder 'your-random-secure-token-here'"):
        create_app(settings)


@pytest.mark.asyncio
async def test_healthz_no_auth_required(client: httpx.AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_auth_missing_token_returns_401(client: httpx.AsyncClient) -> None:
    resp = await client.get("/api/endpoints")
    assert resp.status_code == 401
    assert "Unauthorized" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_auth_invalid_token_returns_401(client: httpx.AsyncClient) -> None:
    resp = await client.get(
        "/api/endpoints",
        headers={"Authorization": "Bearer wrong-token-xyz"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_auth_valid_bearer_token_succeeds(
    client: httpx.AsyncClient, auth_headers: dict[str, str]
) -> None:
    resp = await client.get("/api/endpoints", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_auth_query_param_token_rejected_returns_401(client: httpx.AsyncClient) -> None:
    # Security requirement: API tokens must never be accepted via query parameters
    resp = await client.get(f"/api/endpoints?token={TEST_API_TOKEN}")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_security_headers_present_on_responses(client: httpx.AsyncClient) -> None:
    # Security requirement: CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert "default-src 'self'" in resp.headers.get("content-security-policy", "")
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("x-frame-options") == "DENY"


@pytest.mark.asyncio
async def test_all_openapi_routes_require_authentication_except_healthz(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    # Security requirement: iterate over all routes in OpenAPI schema
    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths", {})
    assert len(paths) > 0

    for path, methods in paths.items():
        if path == "/healthz":
            continue
        # Substitute sample path parameters if any, e.g. {id} -> 1
        test_path = path.replace("{id}", "1")
        for method in methods.keys():
            if method.lower() not in {"get", "post", "put", "delete", "patch"}:
                continue
            # Streaming endpoint tested separately; for basic check verify without auth returns 401
            resp = await client.request(method.upper(), test_path)
            assert resp.status_code == 401, f"Route {method.upper()} {path} failed auth requirement"


@pytest.mark.asyncio
async def test_auth_dev_mode_without_token(caplog: pytest.LogCaptureFixture) -> None:
    dev_settings = Settings(
        database_url="sqlite:///:memory:",
        api_token="",
        dev_mode=True,
    )
    with caplog.at_level("WARNING"):
        dev_app: FastAPI = create_app(dev_settings)

    # Security requirement: Dev mode emits a loud warning
    assert any("SECURITY WARNING" in rec.message for rec in caplog.records)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=dev_app),
        base_url="http://testserver",
    ) as dev_client:
        resp = await dev_client.get("/api/endpoints")
        assert resp.status_code == 200
