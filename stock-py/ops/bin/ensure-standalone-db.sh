#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

TARGET_DB_NAME="${POSTGRES_TARGET_DB:-stock_py}"
TARGET_DB_USER="${POSTGRES_TARGET_USER:-stock_py}"
TARGET_DB_PASSWORD="${POSTGRES_TARGET_PASSWORD:-stock_py}"

PRIMARY_ADMIN_USER="${POSTGRES_PRIMARY_ADMIN_USER:-$TARGET_DB_USER}"
PRIMARY_ADMIN_DB="${POSTGRES_PRIMARY_ADMIN_DB:-$TARGET_DB_NAME}"
LEGACY_ADMIN_USER="${POSTGRES_LEGACY_ADMIN_USER:-stock}"
LEGACY_ADMIN_DB="${POSTGRES_LEGACY_ADMIN_DB:-stock}"

query_psql() {
  admin_user="$1"
  admin_db="$2"
  sql="$3"
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -At -v ON_ERROR_STOP=1 -U "$admin_user" -d "$admin_db" -c "$sql"
}

exec_psql() {
  admin_user="$1"
  admin_db="$2"
  sql="$3"
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$admin_user" -d "$admin_db" -c "$sql"
}

probe_admin() {
  admin_user="$1"
  admin_db="$2"
  docker compose -f "$COMPOSE_FILE" exec -T postgres \
    psql -At -U "$admin_user" -d "$admin_db" -c 'SELECT 1' >/dev/null 2>&1
}

if probe_admin "$PRIMARY_ADMIN_USER" "$PRIMARY_ADMIN_DB"; then
  ADMIN_USER="$PRIMARY_ADMIN_USER"
  ADMIN_DB="$PRIMARY_ADMIN_DB"
elif probe_admin "$LEGACY_ADMIN_USER" "$LEGACY_ADMIN_DB"; then
  ADMIN_USER="$LEGACY_ADMIN_USER"
  ADMIN_DB="$LEGACY_ADMIN_DB"
else
  echo "Unable to connect with either standalone or legacy Postgres admin role." >&2
  exit 1
fi

role_exists="$(query_psql "$ADMIN_USER" "$ADMIN_DB" "SELECT 1 FROM pg_roles WHERE rolname = '$TARGET_DB_USER';")"
if [ "$role_exists" = "1" ]; then
  if [ "$ADMIN_USER" != "$TARGET_DB_USER" ]; then
    exec_psql "$ADMIN_USER" "$ADMIN_DB" "ALTER ROLE \"$TARGET_DB_USER\" WITH LOGIN PASSWORD '$TARGET_DB_PASSWORD';"
  fi
else
  exec_psql "$ADMIN_USER" "$ADMIN_DB" "CREATE ROLE \"$TARGET_DB_USER\" WITH LOGIN PASSWORD '$TARGET_DB_PASSWORD';"
fi

db_exists="$(query_psql "$ADMIN_USER" "$ADMIN_DB" "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB_NAME';")"
if [ "$db_exists" != "1" ]; then
  exec_psql "$ADMIN_USER" "$ADMIN_DB" "CREATE DATABASE \"$TARGET_DB_NAME\" OWNER \"$TARGET_DB_USER\";"
fi

echo "Ensured standalone database baseline: user=$TARGET_DB_USER db=$TARGET_DB_NAME"