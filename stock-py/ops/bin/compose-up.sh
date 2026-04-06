#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

docker compose -f "$COMPOSE_FILE" up -d --build postgres redis kafka kafka-setup clickhouse minio minio-setup

attempts=0
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U stock -d stock >/dev/null 2>&1 \
  || docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U stock_py -d stock_py >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 60 ]; then
    echo "Postgres did not become ready in time" >&2
    exit 1
  fi
  sleep 5
done

"$ROOT_DIR/ops/bin/ensure-standalone-db.sh"

docker compose -f "$COMPOSE_FILE" up -d --build pgbouncer migrate public-api admin-api scheduler event-pipeline retention tradingagents-bridge nginx

attempts=0
until curl -fsS "${STACK_PUBLIC_HEALTH_URL:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}/health}" >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 60 ]; then
    echo "Stack did not become healthy in time" >&2
    exit 1
  fi
  sleep 5
done

echo "Compose stack is healthy."