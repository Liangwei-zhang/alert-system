#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

docker compose -f "$COMPOSE_FILE" up -d --build

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