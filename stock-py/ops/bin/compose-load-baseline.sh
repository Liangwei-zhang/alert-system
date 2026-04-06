#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

export LOAD_TEST_HOST="${LOAD_TEST_HOST:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}}"
export LOAD_RUN_ID="${LOAD_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"

"$ROOT_DIR/ops/bin/compose-up.sh"

docker compose -f "$COMPOSE_FILE" ps > "$ROOT_DIR/ops/reports/load/$LOAD_RUN_ID/compose-ps.txt"
docker compose -f "$COMPOSE_FILE" logs --no-color > "$ROOT_DIR/ops/reports/load/$LOAD_RUN_ID/compose.log"

make -C "$ROOT_DIR" load-baseline