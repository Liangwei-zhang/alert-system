#!/bin/sh
set -eu

if [ -n "${MINIO_ROOT_USER_FILE:-}" ]; then
  export MINIO_ROOT_USER="$(cat "$MINIO_ROOT_USER_FILE")"
fi

if [ -n "${MINIO_ROOT_PASSWORD_FILE:-}" ]; then
  export MINIO_ROOT_PASSWORD="$(cat "$MINIO_ROOT_PASSWORD_FILE")"
fi

: "${MINIO_ROOT_USER:?MINIO_ROOT_USER or MINIO_ROOT_USER_FILE is required}"
: "${MINIO_ROOT_PASSWORD:?MINIO_ROOT_PASSWORD or MINIO_ROOT_PASSWORD_FILE is required}"

exec minio server /data --console-address ":9001"