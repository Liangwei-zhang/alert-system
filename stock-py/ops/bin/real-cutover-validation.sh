#!/bin/sh
set -eu

ROOT_DIR="$(CDPATH= cd -- "$(dirname "$0")/../.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-}"

if [ -z "$PYTHON_BIN" ]; then
  if [ -x "$ROOT_DIR/.venv/bin/python" ]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v python3.13 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.13)"
  else
    PYTHON_BIN="$(command -v python3)"
  fi
fi

resolve_path() {
  case "$1" in
    /*) printf '%s\n' "$1" ;;
    *) printf '%s/%s\n' "$ROOT_DIR" "$1" ;;
  esac
}

lower_value() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

bool_true() {
  case "$(lower_value "${1:-}")" in
    1|true|yes|on) return 0 ;;
    *) return 1 ;;
  esac
}

read_var() {
  eval "printf '%s' \"\${$1:-}\""
}

MISSING_ENV_VALUES=""
VALIDATION_ERRORS=""

require_env() {
  for key in "$@"; do
    value="$(read_var "$key")"
    if [ -z "$value" ]; then
      case " $MISSING_ENV_VALUES " in
        *" $key "*) ;;
        *) MISSING_ENV_VALUES="$MISSING_ENV_VALUES $key" ;;
      esac
    fi
  done
}

record_validation_error() {
  if [ -n "$VALIDATION_ERRORS" ]; then
    VALIDATION_ERRORS="$VALIDATION_ERRORS\n$1"
    return
  fi

  VALIDATION_ERRORS="$1"
}

log_step() {
  printf '\n[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1"
}

kubectl_run() {
  if [ -n "${KUBECTL_CONTEXT:-}" ]; then
    kubectl --context "$KUBECTL_CONTEXT" "$@"
    return
  fi

  if [ -n "${KUBECONFIG:-}" ]; then
    KUBECONFIG="$KUBECONFIG" kubectl "$@"
    return
  fi

  kubectl "$@"
}

run_kubectl_capture() {
  destination="$1"
  shift
  printf '$ %s\n' "kubectl $*" >> "$destination"
  kubectl_run "$@" >> "$destination" 2>&1
}

ENV_FILE="${1:-${CUTOVER_ENV_FILE:-}}"
if [ -z "$ENV_FILE" ]; then
  echo "Usage: CUTOVER_ENV_FILE=path/to/private.env ./ops/bin/real-cutover-validation.sh" >&2
  exit 1
fi

ENV_FILE="$(resolve_path "$ENV_FILE")"
if [ ! -f "$ENV_FILE" ]; then
  echo "Cutover env file not found: $ENV_FILE" >&2
  exit 1
fi

OVERRIDE_RUN_LOAD_BASELINE="${RUN_LOAD_BASELINE-__UNSET__}"
OVERRIDE_RUN_SHADOW_READ="${RUN_SHADOW_READ-__UNSET__}"
OVERRIDE_RUN_DUAL_WRITE="${RUN_DUAL_WRITE-__UNSET__}"
OVERRIDE_RUN_ROLLBACK_VERIFY="${RUN_ROLLBACK_VERIFY-__UNSET__}"
OVERRIDE_RUN_K8S_DIFF="${RUN_K8S_DIFF-__UNSET__}"
OVERRIDE_RUN_K8S_APPLY="${RUN_K8S_APPLY-__UNSET__}"
OVERRIDE_RUN_K8S_ROLLBACK="${RUN_K8S_ROLLBACK-__UNSET__}"
OVERRIDE_RUN_SIGNOFF="${RUN_SIGNOFF-__UNSET__}"

set -a
. "$ENV_FILE"
set +a

if [ "$OVERRIDE_RUN_LOAD_BASELINE" != "__UNSET__" ]; then
  export RUN_LOAD_BASELINE="$OVERRIDE_RUN_LOAD_BASELINE"
fi
if [ "$OVERRIDE_RUN_SHADOW_READ" != "__UNSET__" ]; then
  export RUN_SHADOW_READ="$OVERRIDE_RUN_SHADOW_READ"
fi
if [ "$OVERRIDE_RUN_DUAL_WRITE" != "__UNSET__" ]; then
  export RUN_DUAL_WRITE="$OVERRIDE_RUN_DUAL_WRITE"
fi
if [ "$OVERRIDE_RUN_ROLLBACK_VERIFY" != "__UNSET__" ]; then
  export RUN_ROLLBACK_VERIFY="$OVERRIDE_RUN_ROLLBACK_VERIFY"
fi
if [ "$OVERRIDE_RUN_K8S_DIFF" != "__UNSET__" ]; then
  export RUN_K8S_DIFF="$OVERRIDE_RUN_K8S_DIFF"
fi
if [ "$OVERRIDE_RUN_K8S_APPLY" != "__UNSET__" ]; then
  export RUN_K8S_APPLY="$OVERRIDE_RUN_K8S_APPLY"
fi
if [ "$OVERRIDE_RUN_K8S_ROLLBACK" != "__UNSET__" ]; then
  export RUN_K8S_ROLLBACK="$OVERRIDE_RUN_K8S_ROLLBACK"
fi
if [ "$OVERRIDE_RUN_SIGNOFF" != "__UNSET__" ]; then
  export RUN_SIGNOFF="$OVERRIDE_RUN_SIGNOFF"
fi

cd "$ROOT_DIR"

RUN_TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
export CUTOVER_ENVIRONMENT="${CUTOVER_ENVIRONMENT:-staging}"
export LOAD_TEST_ENVIRONMENT="${LOAD_TEST_ENVIRONMENT:-$CUTOVER_ENVIRONMENT}"
export LOAD_RUN_ID="${LOAD_RUN_ID:-$RUN_TIMESTAMP-real-load}"
export CUTOVER_RUN_ID="${CUTOVER_RUN_ID:-$RUN_TIMESTAMP-real-cutover}"
export LOAD_REPORT_PREFIX="${LOAD_REPORT_PREFIX:-ops/reports/load/$LOAD_RUN_ID/baseline}"
export CUTOVER_REPORT_DIR="${CUTOVER_REPORT_DIR:-ops/reports/cutover/$CUTOVER_RUN_ID}"
export SHADOW_READ_CONFIG_PATH="${SHADOW_READ_CONFIG_PATH:-$CUTOVER_REPORT_DIR/shadow-read-scenarios.json}"
export DUAL_WRITE_CONFIG_PATH="${DUAL_WRITE_CONFIG_PATH:-$CUTOVER_REPORT_DIR/dual-write-scenarios.json}"
export SHADOW_READ_OWNER="${SHADOW_READ_OWNER:-$QA_OWNER}"
export DUAL_WRITE_OWNER="${DUAL_WRITE_OWNER:-$QA_OWNER}"
export LOAD_PUBLIC_HEALTH_URL="${LOAD_PUBLIC_HEALTH_URL:-$STACK_PUBLIC_HEALTH_URL}"
export LOAD_PUBLIC_METRICS_URL="${LOAD_PUBLIC_METRICS_URL:-${STACK_PUBLIC_METRICS_URL:-$LOAD_TEST_HOST/api/monitoring/metrics}}"
export ADMIN_RUNTIME_METRICS_URL="${ADMIN_RUNTIME_METRICS_URL:-$ADMIN_RUNTIME_URL/v1/admin/runtime/metrics}"
export ADMIN_RUNTIME_ALERTS_URL="${ADMIN_RUNTIME_ALERTS_URL:-$ADMIN_RUNTIME_URL/v1/admin/runtime/alerts}"
export CUTOVER_RUNTIME_METRICS_PATH="${CUTOVER_RUNTIME_METRICS_PATH:-$CUTOVER_REPORT_DIR/evidence/admin-runtime-metrics.json}"
export RUNTIME_ALERT_ENV_FILE="${RUNTIME_ALERT_ENV_FILE:-$CUTOVER_REPORT_DIR/evidence/runtime-alert-thresholds.env}"
export RUNTIME_ALERT_JSON_FILE="${RUNTIME_ALERT_JSON_FILE:-$CUTOVER_REPORT_DIR/evidence/runtime-alert-thresholds.json}"
export K8S_OVERLAY_OUTPUT_DIR="${K8S_OVERLAY_OUTPUT_DIR:-$CUTOVER_REPORT_DIR/k8s/overlays/$CUTOVER_ENVIRONMENT}"
export K8S_OVERLAY_JSON_FILE="${K8S_OVERLAY_JSON_FILE:-$K8S_OVERLAY_OUTPUT_DIR/summary.json}"
export K8S_VALIDATION_DIR="${K8S_VALIDATION_DIR:-$CUTOVER_REPORT_DIR/k8s/validation}"
export K8S_KUSTOMIZE_PATH="${K8S_KUSTOMIZE_PATH:-$K8S_OVERLAY_OUTPUT_DIR}"
export K8S_MONITORING_SECRET_NAME="${K8S_MONITORING_SECRET_NAME:-stock-py-monitoring-secret}"
export K8S_ROLLOUT_TIMEOUT="${K8S_ROLLOUT_TIMEOUT:-180s}"
export ROLLOUT_EVIDENCE_PATH="${ROLLOUT_EVIDENCE_PATH:-$CUTOVER_REPORT_DIR/evidence/k8s-rollout-summary.txt}"

if [ -z "${K8S_NAMESPACE:-}" ]; then
  if [ "$CUTOVER_ENVIRONMENT" = "production" ]; then
    export K8S_NAMESPACE="stock-py"
  else
    export K8S_NAMESPACE="stock-py-$CUTOVER_ENVIRONMENT"
  fi
fi

if [ -z "${K8S_INGRESS_HOST:-}" ]; then
  if [ "$CUTOVER_ENVIRONMENT" = "production" ]; then
    export K8S_INGRESS_HOST="stock-py.example.com"
  else
    export K8S_INGRESS_HOST="stock-py-$CUTOVER_ENVIRONMENT.example.com"
  fi
fi

LOAD_REPORT_PREFIX_ABS="$(resolve_path "$LOAD_REPORT_PREFIX")"
CUTOVER_REPORT_DIR_ABS="$(resolve_path "$CUTOVER_REPORT_DIR")"
K8S_KUSTOMIZE_PATH_ABS="$(resolve_path "$K8S_KUSTOMIZE_PATH")"
ROLLOUT_EVIDENCE_PATH_ABS="$(resolve_path "$ROLLOUT_EVIDENCE_PATH")"
LOAD_REPORT_DIR_REL="$(dirname "$LOAD_REPORT_PREFIX")"

mkdir -p "$(dirname "$LOAD_REPORT_PREFIX_ABS")" "$CUTOVER_REPORT_DIR_ABS/evidence"

require_env RELEASE_SHA QA_OWNER BACKEND_OWNER ON_CALL_REVIEWER STACK_PUBLIC_HEALTH_URL ADMIN_RUNTIME_URL ADMIN_RUNTIME_TOKEN

if bool_true "${RUN_LOAD_BASELINE:-true}"; then
  require_env LOAD_TEST_HOST LOAD_TEST_ACCESS_TOKEN LOAD_TEST_REFRESH_TOKEN LOAD_TEST_TRADE_ID LOAD_TEST_TRADE_TOKEN
fi

if bool_true "${RUN_SHADOW_READ:-true}"; then
  require_env LEGACY_BASE_URL SHADOW_READ_SHADOW_BASE_URL LOAD_TEST_ACCESS_TOKEN LOAD_TEST_TRADE_ID
fi

if bool_true "${RUN_DUAL_WRITE:-true}"; then
  require_env DUAL_WRITE_SHADOW_BASE_URL LOAD_TEST_ACCESS_TOKEN LOAD_TEST_TRADE_ID PRIMARY_SUBSCRIPTION_START_URL PRIMARY_ACCOUNT_PROFILE_URL PRIMARY_NOTIFICATION_ACK_URL PRIMARY_NOTIFICATION_READBACK_URL PRIMARY_TRADE_APP_CONFIRM_URL PRIMARY_TRADE_APP_IGNORE_URL PRIMARY_TRADE_APP_ADJUST_URL PRIMARY_TRADE_READBACK_URL PRIMARY_TRADINGAGENTS_SUBMIT_URL PRIMARY_TRADINGAGENTS_ANALYSIS_URL PRIMARY_TRADINGAGENTS_TERMINAL_URL DUAL_WRITE_TRADINGAGENTS_REQUEST_ID DUAL_WRITE_TRADINGAGENTS_JOB_ID DUAL_WRITE_WEBHOOK_SIGNATURE
  if ! bool_true "${DUAL_WRITE_ALLOW_MUTATIONS:-false}"; then
    record_validation_error "Set DUAL_WRITE_ALLOW_MUTATIONS=true before running real dual-write verification."
  fi
fi

if bool_true "${RUN_ROLLBACK_VERIFY:-true}"; then
  require_env BACKUP_DIR
fi

if [ -n "$MISSING_ENV_VALUES" ] || [ -n "$VALIDATION_ERRORS" ]; then
  if [ -n "$MISSING_ENV_VALUES" ]; then
    echo "Missing required environment values:$MISSING_ENV_VALUES" >&2
  fi
  if [ -n "$VALIDATION_ERRORS" ]; then
    printf '%b\n' "$VALIDATION_ERRORS" >&2
  fi
  exit 1
fi

if bool_true "${RUN_LOAD_BASELINE:-true}"; then
  log_step "Running load baseline against $LOAD_TEST_HOST"
  make -C "$ROOT_DIR" load-baseline
  make -C "$ROOT_DIR" load-report-capture
fi

log_step "Initializing cutover report and capturing baseline evidence"
make -C "$ROOT_DIR" cutover-report-init
make -C "$ROOT_DIR" cutover-openapi-diff
make -C "$ROOT_DIR" cutover-evidence-capture

if bool_true "${RUN_SHADOW_READ:-true}"; then
  log_step "Bootstrapping and running shadow-read parity"
  "$PYTHON_BIN" -m infra.core.report_artifacts bootstrap-shadow-read-config --report-dir "$CUTOVER_REPORT_DIR" --config-path "$SHADOW_READ_CONFIG_PATH"
  make -C "$ROOT_DIR" cutover-shadow-read
fi

if bool_true "${RUN_DUAL_WRITE:-true}"; then
  log_step "Bootstrapping and running dual-write parity"
  "$PYTHON_BIN" -m infra.core.report_artifacts bootstrap-dual-write-config --report-dir "$CUTOVER_REPORT_DIR" --config-path "$DUAL_WRITE_CONFIG_PATH"
  make -C "$ROOT_DIR" cutover-dual-write
fi

if bool_true "${RUN_ROLLBACK_VERIFY:-true}"; then
  log_step "Capturing rollback verification evidence"
  make -C "$ROOT_DIR" cutover-rollback-verify
fi

log_step "Calibrating runtime thresholds and rendering K8s overlay"
make -C "$ROOT_DIR" cutover-threshold-calibrate
make -C "$ROOT_DIR" cutover-k8s-overlay
make -C "$ROOT_DIR" ops-k8s-validate

if bool_true "${RUN_K8S_DIFF:-true}" || bool_true "${RUN_K8S_APPLY:-false}" || bool_true "${RUN_K8S_ROLLBACK:-false}"; then
  if ! command -v kubectl >/dev/null 2>&1; then
    echo "kubectl is required for live K8s diff/apply/rollback validation." >&2
    exit 1
  fi

  mkdir -p "$(dirname "$ROLLOUT_EVIDENCE_PATH_ABS")"
  : > "$ROLLOUT_EVIDENCE_PATH_ABS"
  printf 'environment=%s\nnamespace=%s\noverlay=%s\n\n' "$CUTOVER_ENVIRONMENT" "$K8S_NAMESPACE" "$K8S_KUSTOMIZE_PATH_ABS" >> "$ROLLOUT_EVIDENCE_PATH_ABS"

  if bool_true "${RUN_K8S_DIFF:-true}"; then
    log_step "Running kubectl diff against $K8S_KUSTOMIZE_PATH_ABS"
    set +e
    kubectl_run diff -k "$K8S_KUSTOMIZE_PATH_ABS" > "$CUTOVER_REPORT_DIR_ABS/evidence/kubectl-diff.txt" 2>&1
    diff_status=$?
    set -e
    printf '$ kubectl diff -k %s\nexit_code=%s\n\n' "$K8S_KUSTOMIZE_PATH_ABS" "$diff_status" >> "$ROLLOUT_EVIDENCE_PATH_ABS"
    if [ "$diff_status" -gt 1 ]; then
      echo "kubectl diff failed; see $CUTOVER_REPORT_DIR_ABS/evidence/kubectl-diff.txt" >&2
      exit 1
    fi
  fi

  if bool_true "${RUN_K8S_APPLY:-false}"; then
    log_step "Applying generated overlay to cluster"
    run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" apply -k "$K8S_KUSTOMIZE_PATH_ABS"
    run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" wait --namespace "$K8S_NAMESPACE" --for=condition=complete --timeout "$K8S_ROLLOUT_TIMEOUT" job/migrate
    for deployment_name in public-api admin-api scheduler event-pipeline retention tradingagents-bridge; do
      run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" rollout status --namespace "$K8S_NAMESPACE" --timeout "$K8S_ROLLOUT_TIMEOUT" "deployment/$deployment_name"
    done
    run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" get deployment --namespace "$K8S_NAMESPACE"
  fi

  if bool_true "${RUN_K8S_ROLLBACK:-false}"; then
    log_step "Running live rollout undo for application deployments"
    for deployment_name in public-api admin-api scheduler event-pipeline retention tradingagents-bridge; do
      run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" rollout undo --namespace "$K8S_NAMESPACE" "deployment/$deployment_name"
      run_kubectl_capture "$ROLLOUT_EVIDENCE_PATH_ABS" rollout status --namespace "$K8S_NAMESPACE" --timeout "$K8S_ROLLOUT_TIMEOUT" "deployment/$deployment_name"
    done
  fi
fi

if bool_true "${RUN_SIGNOFF:-false}"; then
  log_step "Validating cutover signoff bundle"
  export SIGNOFF_LOAD_REPORT_DIR="$LOAD_REPORT_DIR_REL"
  export SIGNOFF_K8S_VALIDATION_SUMMARY="$K8S_VALIDATION_DIR/summary.json"
  if [ -s "$ROLLOUT_EVIDENCE_PATH_ABS" ]; then
    export SIGNOFF_ROLLOUT_EVIDENCE_PATH="$ROLLOUT_EVIDENCE_PATH"
  fi
  make -C "$ROOT_DIR" cutover-signoff
fi

printf '\nLoad artifacts: %s\nCutover artifacts: %s\n' "$LOAD_REPORT_PREFIX_ABS" "$CUTOVER_REPORT_DIR_ABS"
