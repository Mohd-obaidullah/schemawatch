from __future__ import annotations

import argparse
import logging
import os
import sys

import uvicorn

from schemawatch_api.config import Settings


def main() -> None:
    """Entry point for schemawatch-api CLI / python -m schemawatch_api."""
    parser = argparse.ArgumentParser(description="Run schemawatch API server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind socket host")
    parser.add_argument("--port", type=int, default=8000, help="Bind socket port")
    parser.add_argument("--dev", action="store_true", help="Run with dev mode and reload")
    args = parser.parse_args()

    if args.dev:
        os.environ["SCHEMAWATCH_DEV_MODE"] = "true"

    try:
        settings = Settings()
        settings.validate_token_requirement()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("schemawatch.api")
    logger.info("Starting schemawatch API bound to %s:%d", args.host, args.port)

    uvicorn.run(
        "schemawatch_api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.dev,
    )


if __name__ == "__main__":
    main()
