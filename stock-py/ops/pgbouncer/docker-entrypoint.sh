#!/bin/sh
set -eu

: "${PGBOUNCER_DB_HOST:=postgres}"
: "${PGBOUNCER_DB_PORT:=5432}"
: "${PGBOUNCER_DB_NAME:=stock}"
: "${PGBOUNCER_DB_USER:=stock}"
: "${PGBOUNCER_ADMIN_USERS:=stock}"

if [ -n "${PGBOUNCER_DB_PASSWORD_FILE:-}" ]; then
  export PGBOUNCER_DB_PASSWORD="$(cat "$PGBOUNCER_DB_PASSWORD_FILE")"
fi

: "${PGBOUNCER_DB_PASSWORD:?PGBOUNCER_DB_PASSWORD or PGBOUNCER_DB_PASSWORD_FILE is required}"

cat > /etc/pgbouncer/userlist.txt <<EOF
"${PGBOUNCER_DB_USER}" "${PGBOUNCER_DB_PASSWORD}"
EOF

envsubst < /etc/pgbouncer/pgbouncer.ini.template > /etc/pgbouncer/pgbouncer.ini
exec pgbouncer /etc/pgbouncer/pgbouncer.ini