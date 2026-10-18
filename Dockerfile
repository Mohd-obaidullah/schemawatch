# Stage 1: Build React dashboard
FROM node:20-slim AS web-builder
WORKDIR /app/apps/web
COPY apps/web/package*.json ./
RUN npm ci
COPY apps/web ./
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim AS runner

# Install uv binary from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Install curl for HEALTHCHECK and ca-certificates
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configure Python and application environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" \
    SCHEMAWATCH_DEV_MODE=false

# Copy dependency specifications and lockfile
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/
COPY apps/api/pyproject.toml apps/api/

# Copy application source code and migrations configuration
COPY packages/core packages/core
COPY apps/api apps/api
COPY alembic.ini ./
COPY LICENSE README.md ./

# Install locked dependencies without dev packages
RUN uv sync --frozen --no-dev

# Copy built frontend assets into the directory served by FastAPI
COPY --from=web-builder /app/apps/web/dist ./apps/web/dist

# Create non-root user and persistent data directory
RUN useradd --create-home --home-dir /app appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

# Copy entrypoint script for migrations
COPY scripts/docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "-m", "schemawatch_api", "--host", "0.0.0.0", "--port", "8000"]
