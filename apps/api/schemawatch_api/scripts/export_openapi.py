from __future__ import annotations

import json
from pathlib import Path

from schemawatch_api.app import create_app
from schemawatch_api.config import Settings


def export_openapi(output_path: Path | None = None) -> Path:
    """Generate OpenAPI 3.1 specification JSON from FastAPI app instance."""
    if output_path is None:
        # Default destination: apps/web/openapi.json
        api_root = Path(__file__).resolve().parent.parent.parent
        output_path = api_root.parent / "web" / "openapi.json"

    settings = Settings(dev_mode=True, api_token="")
    app = create_app(settings)
    openapi_schema = app.openapi()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

    return output_path


def main() -> None:
    dest = export_openapi()
    print(f"OpenAPI spec successfully exported to: {dest}")


if __name__ == "__main__":
    main()
