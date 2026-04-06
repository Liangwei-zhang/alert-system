#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

export CUTOVER_RUN_ID="${CUTOVER_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export CUTOVER_REPORT_DIR="${CUTOVER_REPORT_DIR:-$ROOT_DIR/ops/reports/cutover/$CUTOVER_RUN_ID}"

"$ROOT_DIR/ops/bin/compose-up.sh"

make -C "$ROOT_DIR" cutover-openapi-diff

docker compose -f "$COMPOSE_FILE" ps > "$CUTOVER_REPORT_DIR/logs/compose-ps.txt"
docker compose -f "$COMPOSE_FILE" logs --no-color > "$CUTOVER_REPORT_DIR/logs/compose.log"
curl -fsS "${STACK_PUBLIC_HEALTH_URL:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}/health}" > "$CUTOVER_REPORT_DIR/logs/public-health.json"

if [ -n "${ADMIN_RUNTIME_TOKEN:-}" ]; then
  curl -fsS -H "Authorization: Bearer $ADMIN_RUNTIME_TOKEN" "${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}/v1/admin/runtime/metrics" > "$CUTOVER_REPORT_DIR/logs/runtime-metrics.json"
  curl -fsS -H "Authorization: Bearer $ADMIN_RUNTIME_TOKEN" "${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}/v1/admin/runtime/alerts" > "$CUTOVER_REPORT_DIR/logs/runtime-alerts.json"
fi