#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

export LOAD_TEST_HOST="${LOAD_TEST_HOST:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}}"
export LOAD_RUN_ID="${LOAD_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export INTERNAL_SIDECAR_SECRET="${INTERNAL_SIDECAR_SECRET:-stock-py-internal-monitoring}"
export LOAD_PUBLIC_METRICS_TOKEN="${LOAD_PUBLIC_METRICS_TOKEN:-$INTERNAL_SIDECAR_SECRET}"
LOAD_FIXTURE_ENV_FILE="${LOAD_FIXTURE_ENV_FILE:-$ROOT_DIR/ops/reports/load/$LOAD_RUN_ID/fixtures.env}"

"$ROOT_DIR/ops/bin/compose-up.sh"

make -C "$ROOT_DIR" load-bootstrap-fixtures LOAD_RUN_ID="$LOAD_RUN_ID" LOAD_TEST_HOST="$LOAD_TEST_HOST" ADMIN_RUNTIME_URL="${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}" LOAD_FIXTURE_ENV_FILE="ops/reports/load/$LOAD_RUN_ID/fixtures.env" LOAD_FIXTURE_JSON_FILE="ops/reports/load/$LOAD_RUN_ID/fixtures.json"

set -a
. "$LOAD_FIXTURE_ENV_FILE"
set +a

docker compose -f "$COMPOSE_FILE" ps > "$ROOT_DIR/ops/reports/load/$LOAD_RUN_ID/compose-ps.txt"
docker compose -f "$COMPOSE_FILE" logs --no-color > "$ROOT_DIR/ops/reports/load/$LOAD_RUN_ID/compose.log"

make -C "$ROOT_DIR" load-baseline
make -C "$ROOT_DIR" load-report-capture LOAD_REPORT_PREFIX="ops/reports/load/$LOAD_RUN_ID/baseline" LOAD_PUBLIC_HEALTH_URL="${STACK_PUBLIC_HEALTH_URL:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}/health}" LOAD_PUBLIC_METRICS_URL="${STACK_PUBLIC_METRICS_URL:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}/api/monitoring/metrics}" LOAD_PUBLIC_METRICS_TOKEN="$LOAD_PUBLIC_METRICS_TOKEN"