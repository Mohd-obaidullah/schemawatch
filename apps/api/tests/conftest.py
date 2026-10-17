from __future__ import annotations

from collections.abc import AsyncGenerator

import httpx
import pytest
from fastapi import FastAPI
from schemawatch_api.app import create_app
from schemawatch_api.config import Settings

TEST_API_TOKEN = "test-secret-token-12345"


@pytest.fixture
def test_settings(tmp_path: pytest.TempPathFactory) -> Settings:
    """Fixture providing isolated test configuration with in-memory SQLite and auth token."""
    return Settings(
        database_url="sqlite:///:memory:",
        api_token=TEST_API_TOKEN,
        dev_mode=False,
        learn_samples=2,
        sample_rate=1.0,
        cooldown_seconds=60,
        alert_webhook_url="https://hooks.example.com/alerts",
        slack_webhook_url="https://hooks.slack.com/services/test",
    )


@pytest.fixture
def app(test_settings: Settings) -> FastAPI:
    """Fixture providing FastAPI application instance configured for testing."""
    return create_app(test_settings)


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Authorization header fixture for API requests."""
    return {"Authorization": f"Bearer {TEST_API_TOKEN}"}


@pytest.fixture
async def client(app: FastAPI) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Async HTTP test client bound to FastAPI application with ASGITransport."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
