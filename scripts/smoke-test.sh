#!/usr/bin/env bash
# smoke-test.sh - Automated verification of running schemawatch instance
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"

if [ ! -f "${ENV_FILE}" ]; then
    echo "ERROR: .env file not found in ${ROOT_DIR}. Run ./scripts/setup.sh first." >&2
    exit 1
fi

TOKEN=$(grep -E '^SCHEMAWATCH_API_TOKEN=' "${ENV_FILE}" | cut -d'=' -f2- | tr -d '[:space:]')

if [ -z "${TOKEN}" ] || [ "${TOKEN}" = "your-random-secure-token-here" ]; then
    echo "ERROR: Valid SCHEMAWATCH_API_TOKEN not found in .env. Run ./scripts/setup.sh to generate one." >&2
    exit 1
fi

echo "Waiting for schemawatch to become healthy at http://localhost:8000/healthz (timeout 60s)..."
HEALTHY=0
for i in $(seq 1 30); do
    if curl -s -f http://localhost:8000/healthz >/dev/null 2>&1; then
        HEALTHY=1
        break
    fi
    sleep 2
done

if [ "${HEALTHY}" -ne 1 ]; then
    echo "FAIL: schemawatch failed to become healthy at http://localhost:8000/healthz within 60s" >&2
    exit 1
fi
echo "Service is healthy!"

RUN_ID=$(date +%s)
ENDPOINT="GET /v1/smoke-${RUN_ID}"

echo "Sending 10 normal baseline learning samples to ${ENDPOINT}..."
for i in $(seq 1 10); do
    curl -s -f -X POST http://localhost:8000/api/ingest \
        -H "Authorization: Bearer ${TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{\"vendor\":\"payco\",\"endpoint\":\"${ENDPOINT}\",\"payload\":{\"user_id\":${i},\"amount\":10.5}}" >/dev/null
done

echo "Sending 1 type-drift sample (user_id changed from integer to string)..."
RESPONSE=$(curl -s -f -X POST http://localhost:8000/api/ingest \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"vendor\":\"payco\",\"endpoint\":\"${ENDPOINT}\",\"payload\":{\"user_id\":\"string_user_id_sample\",\"amount\":10.5}}")

if echo "${RESPONSE}" | grep -q '"changes_detected":1'; then
    echo "PASS: Smoke test passed! Drift detected successfully (changes_detected: 1)."
    exit 0
else
    echo "FAIL: Expected changes_detected: 1, got response: ${RESPONSE}" >&2
    exit 1
fi
