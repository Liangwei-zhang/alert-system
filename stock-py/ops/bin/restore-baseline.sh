#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"
BACKUP_DIR="${BACKUP_DIR:-}"
SECRET_DIR="${OPS_SECRET_DIR:-$ROOT_DIR/ops/secrets/dev}"
POSTGRES_DB_NAME="${POSTGRES_DB_NAME:-stock_py}"
POSTGRES_USER_NAME="${POSTGRES_USER_NAME:-stock_py}"
POSTGRES_DUMP_NAME="${POSTGRES_DUMP_NAME:-stock_py.dump}"
LEGACY_POSTGRES_DUMP_NAME="${LEGACY_POSTGRES_DUMP_NAME:-stock.dump}"
DUMP_PATH="$BACKUP_DIR/postgres/$POSTGRES_DUMP_NAME"

if [ -n "$BACKUP_DIR" ] && [ ! -f "$DUMP_PATH" ]; then
  DUMP_PATH="$BACKUP_DIR/postgres/$LEGACY_POSTGRES_DUMP_NAME"
fi

if [ -z "$BACKUP_DIR" ] || [ ! -f "$DUMP_PATH" ]; then
  echo "Set BACKUP_DIR to a valid baseline backup directory." >&2
  exit 1
fi

docker compose -f "$COMPOSE_FILE" up -d postgres minio pgbouncer redis kafka clickhouse

attempts=0
until docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "$POSTGRES_USER_NAME" -d "$POSTGRES_DB_NAME" >/dev/null 2>&1; do
  attempts=$((attempts + 1))
  if [ "$attempts" -ge 30 ]; then
    echo "Postgres did not become ready in time" >&2
    exit 1
  fi
  sleep 2
done

docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$POSTGRES_USER_NAME" -d "$POSTGRES_DB_NAME" -c 'DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;'
docker compose -f "$COMPOSE_FILE" exec -T postgres /bin/sh -c "pg_restore -U $POSTGRES_USER_NAME -d $POSTGRES_DB_NAME --clean --if-exists --no-owner --no-privileges" < "$DUMP_PATH"

OPS_SECRET_DIR="$SECRET_DIR" OPS_BACKUP_DIR="$BACKUP_DIR/minio" docker compose -f "$COMPOSE_FILE" --profile ops run --rm mc /bin/sh -ec '
MINIO_USER=$(cat /run/secrets/minio_root_user)
MINIO_PASS=$(cat /run/secrets/minio_root_password)
mc alias set local http://minio:9000 "$MINIO_USER" "$MINIO_PASS"
mc mb --ignore-existing local/stock-py
mc mirror --overwrite /backup/stock-py local/stock-py
'

echo "Authoritative state restored. Start the app stack and replay Kafka / ClickHouse from PostgreSQL and archives if needed."