#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/ops/docker-compose.yml"

export CUTOVER_RUN_ID="${CUTOVER_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
export CUTOVER_REPORT_DIR="${CUTOVER_REPORT_DIR:-$ROOT_DIR/ops/reports/cutover/$CUTOVER_RUN_ID}"
export CUTOVER_ENVIRONMENT="${CUTOVER_ENVIRONMENT:-staging}"
export LOAD_TEST_HOST="${LOAD_TEST_HOST:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}}"
CUTOVER_FIXTURE_ENV_FILE="${CUTOVER_FIXTURE_ENV_FILE:-$CUTOVER_REPORT_DIR/rehearsal.env}"

"$ROOT_DIR/ops/bin/compose-up.sh"

make -C "$ROOT_DIR" cutover-bootstrap-fixtures CUTOVER_REPORT_DIR="ops/reports/cutover/$CUTOVER_RUN_ID" LOAD_TEST_HOST="$LOAD_TEST_HOST" ADMIN_RUNTIME_URL="${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}" CUTOVER_FIXTURE_ENV_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/rehearsal.env" CUTOVER_FIXTURE_JSON_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/rehearsal.json"

set -a
. "$CUTOVER_FIXTURE_ENV_FILE"
set +a

make -C "$ROOT_DIR" cutover-openapi-diff

docker compose -f "$COMPOSE_FILE" ps > "$CUTOVER_REPORT_DIR/logs/compose-ps.txt"
docker compose -f "$COMPOSE_FILE" logs --no-color > "$CUTOVER_REPORT_DIR/logs/compose.log"
make -C "$ROOT_DIR" cutover-evidence-capture CUTOVER_REPORT_DIR="ops/reports/cutover/$CUTOVER_RUN_ID" STACK_PUBLIC_HEALTH_URL="${STACK_PUBLIC_HEALTH_URL:-http://127.0.0.1:${NGINX_HOST_PORT:-8080}/health}" ADMIN_RUNTIME_METRICS_URL="${ADMIN_RUNTIME_METRICS_URL:-${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}/v1/admin/runtime/metrics}" ADMIN_RUNTIME_ALERTS_URL="${ADMIN_RUNTIME_ALERTS_URL:-${ADMIN_RUNTIME_URL:-http://127.0.0.1:8001}/v1/admin/runtime/alerts}" ADMIN_RUNTIME_TOKEN="${ADMIN_RUNTIME_TOKEN:-}"
make -C "$ROOT_DIR" cutover-threshold-calibrate CUTOVER_REPORT_DIR="ops/reports/cutover/$CUTOVER_RUN_ID" CUTOVER_RUNTIME_METRICS_PATH="ops/reports/cutover/$CUTOVER_RUN_ID/evidence/admin-runtime-metrics.json" RUNTIME_ALERT_ENV_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/evidence/runtime-alert-thresholds.env" RUNTIME_ALERT_JSON_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/evidence/runtime-alert-thresholds.json"
make -C "$ROOT_DIR" cutover-k8s-overlay CUTOVER_ENVIRONMENT="$CUTOVER_ENVIRONMENT" CUTOVER_REPORT_DIR="ops/reports/cutover/$CUTOVER_RUN_ID" RUNTIME_ALERT_ENV_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/evidence/runtime-alert-thresholds.env" K8S_OVERLAY_OUTPUT_DIR="ops/reports/cutover/$CUTOVER_RUN_ID/k8s/overlays/$CUTOVER_ENVIRONMENT" K8S_OVERLAY_JSON_FILE="ops/reports/cutover/$CUTOVER_RUN_ID/k8s/overlays/$CUTOVER_ENVIRONMENT/summary.json" RELEASE_SHA="${RELEASE_SHA:-}" K8S_NAMESPACE="${K8S_NAMESPACE:-}" K8S_INGRESS_HOST="${K8S_INGRESS_HOST:-}" K8S_RELEASE_IMAGE="${K8S_RELEASE_IMAGE:-}" K8S_BASE_KUSTOMIZE_PATH="${K8S_BASE_KUSTOMIZE_PATH:-}" K8S_MONITORING_SECRET_NAME="${K8S_MONITORING_SECRET_NAME:-stock-py-monitoring-secret}"
make -C "$ROOT_DIR" ops-k8s-validate K8S_KUSTOMIZE_PATH="ops/reports/cutover/$CUTOVER_RUN_ID/k8s/overlays/$CUTOVER_ENVIRONMENT" K8S_VALIDATION_DIR="ops/reports/cutover/$CUTOVER_RUN_ID/k8s/validation"