PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else command -v python3.13 2>/dev/null || command -v python3 2>/dev/null; fi)
PIP ?= $(PYTHON) -m pip
ALEMBIC ?= $(PYTHON) -c "from alembic.config import main; main()"
LOCUST ?= $(PYTHON) -m locust
LOAD_USERS ?= 5
LOAD_SPAWN_RATE ?= 1
LOAD_DURATION ?= 1m
LOAD_TEST_ENVIRONMENT ?= staging
LOAD_RUN_ID ?= $(shell date -u +%Y%m%dT%H%M%SZ)
LOAD_REPORT_PREFIX ?= ops/reports/load/$(LOAD_RUN_ID)/baseline
LOAD_FIXTURE_ENV_FILE ?= ops/reports/load/$(LOAD_RUN_ID)/fixtures.env
LOAD_FIXTURE_JSON_FILE ?= ops/reports/load/$(LOAD_RUN_ID)/fixtures.json
LOAD_PUBLIC_HEALTH_URL ?= $(LOAD_TEST_HOST)/health
LOAD_PUBLIC_METRICS_URL ?= $(LOAD_TEST_HOST)/api/monitoring/metrics
LOAD_PUBLIC_METRICS_TOKEN ?=
CUTOVER_ENVIRONMENT ?= staging
CUTOVER_RUN_ID ?= $(shell date -u +%Y%m%dT%H%M%SZ)
CUTOVER_REPORT_DIR ?= ops/reports/cutover/$(CUTOVER_RUN_ID)
CUTOVER_FIXTURE_ENV_FILE ?= $(CUTOVER_REPORT_DIR)/rehearsal.env
CUTOVER_FIXTURE_JSON_FILE ?= $(CUTOVER_REPORT_DIR)/rehearsal.json
CUTOVER_RUNTIME_METRICS_PATH ?= $(CUTOVER_REPORT_DIR)/evidence/admin-runtime-metrics.json
RUNTIME_ALERT_ENV_FILE ?= $(CUTOVER_REPORT_DIR)/evidence/runtime-alert-thresholds.env
RUNTIME_ALERT_JSON_FILE ?= $(CUTOVER_REPORT_DIR)/evidence/runtime-alert-thresholds.json
SHADOW_READ_REPORT_DIR ?= $(CUTOVER_REPORT_DIR)
SHADOW_READ_CONFIG_PATH ?= $(SHADOW_READ_REPORT_DIR)/shadow-read-scenarios.json
SHADOW_READ_DURATION_SECONDS ?= 900
SHADOW_READ_INTERVAL_SECONDS ?= 30
SHADOW_READ_TIMEOUT_SECONDS ?= 10
SHADOW_READ_OWNER ?= $(QA_OWNER)
SHADOW_READ_SCOPE ?=
SHADOW_READ_PRIMARY_LABEL ?= legacy
SHADOW_READ_SHADOW_LABEL ?= python
DUAL_WRITE_REPORT_DIR ?= $(CUTOVER_REPORT_DIR)
DUAL_WRITE_CONFIG_PATH ?= $(DUAL_WRITE_REPORT_DIR)/dual-write-scenarios.json
DUAL_WRITE_TIMEOUT_SECONDS ?= 10
DUAL_WRITE_OWNER ?= $(QA_OWNER)
DUAL_WRITE_SCOPE ?=
DUAL_WRITE_CONTAINMENT_DECISION ?=
DUAL_WRITE_PRIMARY_LABEL ?= legacy
DUAL_WRITE_SHADOW_LABEL ?= python
DUAL_WRITE_ALLOW_MUTATIONS ?= false
ROLLBACK_VERIFY_REPORT_DIR ?= $(CUTOVER_REPORT_DIR)
ROLLBACK_VERIFY_TIMEOUT_SECONDS ?= 10
ROLLBACK_VERIFY_TRIGGER_USED ?=
ROLLBACK_VERIFY_SMOKE_SUITE ?=
ROLLBACK_VERIFY_BACKLOG_RECONCILIATION ?=
ROLLBACK_VERIFY_FINAL_DECISION ?=
ROLLBACK_VERIFY_RESTORE_COMMAND ?=
SIGNOFF_LOAD_REPORT_DIR ?=
SIGNOFF_K8S_VALIDATION_SUMMARY ?= $(CUTOVER_REPORT_DIR)/k8s/validation/summary.json
SIGNOFF_ROLLOUT_EVIDENCE_PATH ?=
K8S_VALIDATION_DIR ?= $(CUTOVER_REPORT_DIR)/k8s
K8S_KUSTOMIZE_PATH ?= ops/k8s/base
K8S_OVERLAY_OUTPUT_DIR ?= $(CUTOVER_REPORT_DIR)/k8s/overlays/$(CUTOVER_ENVIRONMENT)
K8S_OVERLAY_JSON_FILE ?= $(K8S_OVERLAY_OUTPUT_DIR)/summary.json
K8S_BASE_KUSTOMIZE_PATH ?=
K8S_NAMESPACE ?=
K8S_INGRESS_HOST ?=
K8S_RELEASE_IMAGE ?= $(if $(RELEASE_SHA),ghcr.io/openclaw/stock-py:$(RELEASE_SHA),)
K8S_MONITORING_SECRET_NAME ?= stock-py-monitoring-secret
OPENAPI_BASELINE_DIR ?= tests/contract/snapshots
OPENAPI_ARTIFACT_DIR ?= $(CUTOVER_REPORT_DIR)/openapi
ADMIN_RUNTIME_METRICS_URL ?= $(ADMIN_RUNTIME_URL)/v1/admin/runtime/metrics
ADMIN_RUNTIME_ALERTS_URL ?= $(ADMIN_RUNTIME_URL)/v1/admin/runtime/alerts
RELEASE_SHA ?=
QA_OWNER ?=
BACKEND_OWNER ?=
ON_CALL_REVIEWER ?=
BACKUP_DIR ?=

.PHONY: install format lint test test-unit test-integration test-contract test-e2e test-qa test-load-import qa-ci load-check-env load-help load-bootstrap-fixtures load-report-init load-report-finalize load-report-capture load-baseline cutover-bootstrap-fixtures cutover-report-init cutover-evidence-capture cutover-shadow-read cutover-dual-write cutover-rollback-verify cutover-signoff cutover-threshold-calibrate cutover-k8s-overlay cutover-openapi-diff migrate migrate-down migration-revision run-public-api run-admin-api run-scheduler ops-stack-up ops-compose-load-baseline ops-compose-cutover-rehearsal ops-k8s-validate ops-backup-baseline ops-restore-baseline

install:
	$(PIP) install -r requirements.txt

format:
	$(PYTHON) -m black .
	$(PYTHON) -m isort .

lint:
	$(PYTHON) -m black --check .
	$(PYTHON) -m isort --check-only .

test:
	$(PYTHON) -m pytest

test-unit:
	$(PYTHON) -m pytest tests/unit -q

test-integration:
	$(PYTHON) -m pytest tests/integration -q

test-contract:
	$(PYTHON) -m pytest tests/contract -q

test-e2e:
	$(PYTHON) -m pytest tests/e2e -q

test-qa:
	$(PYTHON) -m pytest tests/contract tests/e2e -q

test-load-import:
	$(PYTHON) -m compileall -q tests/load
	$(PYTHON) -c "import tests.load.locustfile"

qa-ci: test-unit test-integration test-qa test-load-import

load-check-env:
	$(PYTHON) -m tests.load.validate_env

load-help:
	$(LOCUST) -f tests/load/locustfile.py --help

load-bootstrap-fixtures:
	$(PYTHON) -m infra.core.local_rehearsal bootstrap-fixtures --output-env "$(LOAD_FIXTURE_ENV_FILE)" --output-json "$(LOAD_FIXTURE_JSON_FILE)" --host "$(LOAD_TEST_HOST)" --admin-url "$(ADMIN_RUNTIME_URL)"

load-report-init:
	$(PYTHON) -m infra.core.report_artifacts load-baseline --report-prefix "$(LOAD_REPORT_PREFIX)" --environment "$(LOAD_TEST_ENVIRONMENT)" --release-sha "$(RELEASE_SHA)" --run-id "$(LOAD_RUN_ID)" --qa-owner "$(QA_OWNER)" --backend-owner "$(BACKEND_OWNER)" --host "$(LOAD_TEST_HOST)" --users "$(LOAD_USERS)" --spawn-rate "$(LOAD_SPAWN_RATE)" --duration "$(LOAD_DURATION)"

load-report-capture:
	$(PYTHON) -m infra.core.report_artifacts capture-load-evidence --report-prefix "$(LOAD_REPORT_PREFIX)" --public-health-url "$(LOAD_PUBLIC_HEALTH_URL)" --public-metrics-url "$(LOAD_PUBLIC_METRICS_URL)" --public-metrics-token "$(LOAD_PUBLIC_METRICS_TOKEN)"

load-report-finalize:
	$(PYTHON) -m infra.core.report_artifacts capture-load-evidence --report-prefix "$(LOAD_REPORT_PREFIX)"

load-baseline:
	$(MAKE) load-check-env
	$(MAKE) load-report-init
	@mkdir -p "$(dir $(LOAD_REPORT_PREFIX))"
	$(LOCUST) -f tests/load/locustfile.py --headless --only-summary --csv "$(LOAD_REPORT_PREFIX)" --html "$(LOAD_REPORT_PREFIX).html" --host "$(LOAD_TEST_HOST)" -u "$(LOAD_USERS)" -r "$(LOAD_SPAWN_RATE)" -t "$(LOAD_DURATION)"
	$(MAKE) load-report-finalize

cutover-bootstrap-fixtures:
	$(PYTHON) -m infra.core.local_rehearsal bootstrap-fixtures --output-env "$(CUTOVER_FIXTURE_ENV_FILE)" --output-json "$(CUTOVER_FIXTURE_JSON_FILE)" --host "$(LOAD_TEST_HOST)" --admin-url "$(ADMIN_RUNTIME_URL)"

cutover-report-init:
	$(PYTHON) -m infra.core.report_artifacts cutover-rehearsal --report-dir "$(CUTOVER_REPORT_DIR)" --environment "$(CUTOVER_ENVIRONMENT)" --release-sha "$(RELEASE_SHA)" --run-id "$(CUTOVER_RUN_ID)" --qa-owner "$(QA_OWNER)" --backend-owner "$(BACKEND_OWNER)" --on-call-reviewer "$(ON_CALL_REVIEWER)"

cutover-evidence-capture:
	$(PYTHON) -m infra.core.report_artifacts capture-cutover-evidence --report-dir "$(CUTOVER_REPORT_DIR)" --public-health-url "$(STACK_PUBLIC_HEALTH_URL)" --admin-runtime-metrics-url "$(ADMIN_RUNTIME_METRICS_URL)" --admin-runtime-alerts-url "$(ADMIN_RUNTIME_ALERTS_URL)" --admin-token "$(ADMIN_RUNTIME_TOKEN)"

cutover-shadow-read:
	$(PYTHON) -m infra.core.report_artifacts capture-shadow-read --report-dir "$(SHADOW_READ_REPORT_DIR)" --config-path "$(SHADOW_READ_CONFIG_PATH)" --duration-seconds "$(SHADOW_READ_DURATION_SECONDS)" --interval-seconds "$(SHADOW_READ_INTERVAL_SECONDS)" --timeout-seconds "$(SHADOW_READ_TIMEOUT_SECONDS)" --owner "$(SHADOW_READ_OWNER)" --scope-label "$(SHADOW_READ_SCOPE)" --primary-label "$(SHADOW_READ_PRIMARY_LABEL)" --shadow-label "$(SHADOW_READ_SHADOW_LABEL)"

cutover-dual-write:
	DUAL_WRITE_ALLOW_MUTATIONS="$(DUAL_WRITE_ALLOW_MUTATIONS)" $(PYTHON) -m infra.core.report_artifacts capture-dual-write --report-dir "$(DUAL_WRITE_REPORT_DIR)" --config-path "$(DUAL_WRITE_CONFIG_PATH)" --timeout-seconds "$(DUAL_WRITE_TIMEOUT_SECONDS)" --owner "$(DUAL_WRITE_OWNER)" --scope-label "$(DUAL_WRITE_SCOPE)" --containment-decision "$(DUAL_WRITE_CONTAINMENT_DECISION)" --primary-label "$(DUAL_WRITE_PRIMARY_LABEL)" --shadow-label "$(DUAL_WRITE_SHADOW_LABEL)"

cutover-rollback-verify:
	@test -n "$(BACKUP_DIR)" || (echo "Usage: make cutover-rollback-verify BACKUP_DIR=.local/backups/<timestamp>" && exit 1)
	$(PYTHON) -m infra.core.report_artifacts capture-rollback-verification --report-dir "$(ROLLBACK_VERIFY_REPORT_DIR)" --backup-dir "$(BACKUP_DIR)" --trigger-used "$(ROLLBACK_VERIFY_TRIGGER_USED)" --smoke-suite-rerun "$(ROLLBACK_VERIFY_SMOKE_SUITE)" --backlog-reconciliation "$(ROLLBACK_VERIFY_BACKLOG_RECONCILIATION)" --final-decision "$(ROLLBACK_VERIFY_FINAL_DECISION)" --restore-command "$(ROLLBACK_VERIFY_RESTORE_COMMAND)" --public-health-url "$(STACK_PUBLIC_HEALTH_URL)" --admin-runtime-metrics-url "$(ADMIN_RUNTIME_METRICS_URL)" --admin-runtime-alerts-url "$(ADMIN_RUNTIME_ALERTS_URL)" --admin-token "$(ADMIN_RUNTIME_TOKEN)" --timeout-seconds "$(ROLLBACK_VERIFY_TIMEOUT_SECONDS)"

cutover-signoff:
	@test -n "$(SIGNOFF_LOAD_REPORT_DIR)" || (echo "Usage: make cutover-signoff SIGNOFF_LOAD_REPORT_DIR=ops/reports/load/<run_id> [CUTOVER_REPORT_DIR=ops/reports/cutover/<run_id>]" && exit 1)
	$(PYTHON) -m infra.core.report_artifacts validate-cutover-signoff --report-dir "$(CUTOVER_REPORT_DIR)" --load-report-dir "$(SIGNOFF_LOAD_REPORT_DIR)" --backup-dir "$(BACKUP_DIR)" --k8s-validation-summary "$(SIGNOFF_K8S_VALIDATION_SUMMARY)" --rollout-evidence-path "$(SIGNOFF_ROLLOUT_EVIDENCE_PATH)"

cutover-threshold-calibrate:
	$(PYTHON) -m infra.core.local_rehearsal calibrate-thresholds --metrics-path "$(CUTOVER_RUNTIME_METRICS_PATH)" --output-env "$(RUNTIME_ALERT_ENV_FILE)" --output-json "$(RUNTIME_ALERT_JSON_FILE)"

cutover-k8s-overlay:
	K8S_RELEASE_IMAGE="$(K8S_RELEASE_IMAGE)" K8S_NAMESPACE="$(K8S_NAMESPACE)" K8S_INGRESS_HOST="$(K8S_INGRESS_HOST)" K8S_BASE_KUSTOMIZE_PATH="$(K8S_BASE_KUSTOMIZE_PATH)" K8S_MONITORING_SECRET_NAME="$(K8S_MONITORING_SECRET_NAME)" $(PYTHON) -m infra.core.local_rehearsal render-k8s-overrides --runtime-alert-env "$(RUNTIME_ALERT_ENV_FILE)" --output-dir "$(K8S_OVERLAY_OUTPUT_DIR)" --environment "$(CUTOVER_ENVIRONMENT)" --output-json "$(K8S_OVERLAY_JSON_FILE)"

cutover-openapi-diff:
	$(MAKE) cutover-report-init
	$(PYTHON) -m infra.core.openapi_artifacts cutover-diff --output-dir "$(OPENAPI_ARTIFACT_DIR)" --baseline-dir "$(OPENAPI_BASELINE_DIR)" --release-sha "$(RELEASE_SHA)" --run-id "$(CUTOVER_RUN_ID)"

migrate:
	$(ALEMBIC) upgrade head

migrate-down:
	$(ALEMBIC) downgrade -1

migration-revision:
	@test -n "$(message)" || (echo "Usage: make migration-revision message=\"describe change\"" && exit 1)
	$(ALEMBIC) revision -m "$(message)"

run-public-api:
	$(PYTHON) -m uvicorn apps.public_api.main:app --reload --host 0.0.0.0 --port 8000

run-admin-api:
	$(PYTHON) -m uvicorn apps.admin_api.main:app --reload --host 0.0.0.0 --port 8001

run-scheduler:
	$(PYTHON) -m apps.scheduler.main

ops-stack-up:
	./ops/bin/compose-up.sh

ops-compose-load-baseline:
	./ops/bin/compose-load-baseline.sh

ops-compose-cutover-rehearsal:
	./ops/bin/compose-cutover-rehearsal.sh

ops-k8s-validate:
	OUTPUT_DIR="$(K8S_VALIDATION_DIR)" KUSTOMIZE_PATH="$(K8S_KUSTOMIZE_PATH)" ./ops/bin/k8s-validate.sh

ops-backup-baseline:
	./ops/bin/backup-baseline.sh

ops-restore-baseline:
	@test -n "$(BACKUP_DIR)" || (echo "Usage: make ops-restore-baseline BACKUP_DIR=.local/backups/<timestamp>" && exit 1)
	BACKUP_DIR="$(BACKUP_DIR)" ./ops/bin/restore-baseline.sh