#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"
SECRET_DIR="${OPS_SECRET_DIR:-$ROOT_DIR/ops/secrets/dev}"
BACKUP_RUN_ID="${BACKUP_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
BACKUP_DIR="${BACKUP_DIR:-$ROOT_DIR/.local/backups/$BACKUP_RUN_ID}"

mkdir -p "$BACKUP_DIR/postgres" "$BACKUP_DIR/minio"

docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U stock -d stock -Fc > "$BACKUP_DIR/postgres/stock.dump"

OPS_SECRET_DIR="$SECRET_DIR" OPS_BACKUP_DIR="$BACKUP_DIR/minio" docker compose -f "$COMPOSE_FILE" --profile ops run --rm mc /bin/sh -ec '
MINIO_USER=$(cat /run/secrets/minio_root_user)
MINIO_PASS=$(cat /run/secrets/minio_root_password)
mc alias set local http://minio:9000 "$MINIO_USER" "$MINIO_PASS"
mc mirror --overwrite local/stock-py /backup/stock-py
'

docker compose -f "$COMPOSE_FILE" ps > "$BACKUP_DIR/compose-ps.txt"

echo "Baseline backup written to $BACKUP_DIR"