#!/bin/sh
set -e

# Validate API token requirement before touching database or running migrations
if [ "${SCHEMAWATCH_DEV_MODE}" != "true" ]; then
    TOKEN=$(printf "%s" "${SCHEMAWATCH_API_TOKEN}" | tr -d '[:space:]')
    if [ -z "${TOKEN}" ] || [ "${TOKEN}" = "your-random-secure-token-here" ]; then
        echo "ERROR: SCHEMAWATCH_API_TOKEN is not set. Create .env from .env.example and set a token. Generate one with:" >&2
        echo '  python -c "import secrets; print(secrets.token_urlsafe(32))"' >&2
        exit 1
    fi
fi

# Wait for database connection if external DB is configured
echo "Waiting for database connection and applying migrations..."
python -c "
import time, sys, os
from sqlalchemy import create_engine

db_url = os.environ.get('SCHEMAWATCH_DATABASE_URL', 'sqlite:///schemawatch.db')
engine = create_engine(db_url)
for i in range(30):
    try:
        with engine.connect():
            break
    except Exception as e:
        if i == 29:
            print(f'Database connection failed after 30s: {e}', file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
"

# Apply Alembic migrations
alembic upgrade head

# Execute main process
exec "$@"
