from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from schemawatch_api.app import create_app
from schemawatch_api.config import Settings


@pytest.mark.asyncio
async def test_frontend_dist_mounted_with_spa_fallback(tmp_path: Path) -> None:
    # Setup test dist in apps/web/dist
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    web_dist = repo_root / "apps" / "web" / "dist"
    web_dist.mkdir(parents=True, exist_ok=True)
    index_file = web_dist / "index.html"
    index_content = (
        "<!DOCTYPE html><html><head><title>schemawatch</title></head>"
        "<body><div id='root'></div></body></html>"
    )
    index_file.write_text(index_content, encoding="utf-8")

    assets_dir = web_dist / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    asset_file = assets_dir / "test.js"
    asset_file.write_text("console.log('test');", encoding="utf-8")

    try:
        settings = Settings(
            database_url="sqlite:///:memory:",
            dev_mode=True,
            api_token="",
        )
        app = create_app(settings)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            # 1. Root returns index.html
            res_root = await client.get("/")
            assert res_root.status_code == 200
            assert "schemawatch" in res_root.text

            # 2. Existing static asset returns the file
            res_asset = await client.get("/assets/test.js")
            assert res_asset.status_code == 200
            assert "console.log('test')" in res_asset.text

            # 3. SPA client-side route (e.g. /alerts) falls back to index.html
            res_spa = await client.get("/alerts")
            assert res_spa.status_code == 200
            assert "schemawatch" in res_spa.text

            # 4. API routes are not intercepted by the SPA fallback
            res_api = await client.get("/healthz")
            assert res_api.status_code == 200
            assert res_api.json()["status"] == "ok"

    finally:
        # Cleanup temporary test files if needed
        if asset_file.exists():
            asset_file.unlink()
