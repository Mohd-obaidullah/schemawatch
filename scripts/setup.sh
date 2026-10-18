#!/usr/bin/env bash
# setup.sh - Automated, safe first-time environment setup for Linux and macOS
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_EXAMPLE="${ROOT_DIR}/.env.example"
ENV_FILE="${ROOT_DIR}/.env"

if [ ! -f "${ENV_EXAMPLE}" ]; then
    echo "ERROR: .env.example not found in ${ROOT_DIR}" >&2
    exit 1
fi

if [ -f "${ENV_FILE}" ]; then
    echo ".env already exists. Preserving existing configuration."
else
    TOKEN=""
    if command -v python3 >/dev/null 2>&1; then
        TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || true)
    elif command -v python >/dev/null 2>&1; then
        TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || true)
    fi

    if [ -z "${TOKEN}" ] && command -v openssl >/dev/null 2>&1; then
        TOKEN=$(openssl rand -base64 32 | tr -d '=/+' | cut -c1-43)
    fi

    if [ -z "${TOKEN}" ]; then
        echo "ERROR: Failed to generate a secure token. Ensure python3 or openssl is installed." >&2
        exit 1
    fi

    # Create .env from template with secure defaults
    sed -e "s|^SCHEMAWATCH_API_TOKEN=.*|SCHEMAWATCH_API_TOKEN=${TOKEN}|" \
        -e "s|^SCHEMAWATCH_DEV_MODE=.*|SCHEMAWATCH_DEV_MODE=false|" \
        "${ENV_EXAMPLE}" > "${ENV_FILE}"

    echo "Token saved to .env"
fi

echo ""
echo "Next command to run:"
echo "  docker compose up --build -d"
echo "  ./scripts/smoke-test.sh"
