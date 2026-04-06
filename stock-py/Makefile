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
CUTOVER_ENVIRONMENT ?= staging
CUTOVER_RUN_ID ?= $(shell date -u +%Y%m%dT%H%M%SZ)
CUTOVER_REPORT_DIR ?= ops/reports/cutover/$(CUTOVER_RUN_ID)
OPENAPI_BASELINE_DIR ?= tests/contract/snapshots
OPENAPI_ARTIFACT_DIR ?= $(CUTOVER_REPORT_DIR)/openapi
RELEASE_SHA ?=
QA_OWNER ?=
BACKEND_OWNER ?=
ON_CALL_REVIEWER ?=
BACKUP_DIR ?=

.PHONY: install format lint test test-unit test-integration test-contract test-e2e test-qa test-load-import qa-ci load-check-env load-help load-report-init load-baseline cutover-report-init cutover-openapi-diff migrate migrate-down migration-revision run-public-api run-admin-api run-scheduler ops-stack-up ops-compose-load-baseline ops-compose-cutover-rehearsal ops-backup-baseline ops-restore-baseline

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

load-report-init:
	$(PYTHON) -m infra.core.report_artifacts load-baseline --report-prefix "$(LOAD_REPORT_PREFIX)" --environment "$(LOAD_TEST_ENVIRONMENT)" --release-sha "$(RELEASE_SHA)" --run-id "$(LOAD_RUN_ID)" --qa-owner "$(QA_OWNER)" --backend-owner "$(BACKEND_OWNER)" --host "$(LOAD_TEST_HOST)" --users "$(LOAD_USERS)" --spawn-rate "$(LOAD_SPAWN_RATE)" --duration "$(LOAD_DURATION)"

load-baseline:
	$(MAKE) load-check-env
	$(MAKE) load-report-init
	@mkdir -p "$(dir $(LOAD_REPORT_PREFIX))"
	$(LOCUST) -f tests/load/locustfile.py --headless --only-summary --csv "$(LOAD_REPORT_PREFIX)" --html "$(LOAD_REPORT_PREFIX).html" --host "$(LOAD_TEST_HOST)" -u "$(LOAD_USERS)" -r "$(LOAD_SPAWN_RATE)" -t "$(LOAD_DURATION)"

cutover-report-init:
	$(PYTHON) -m infra.core.report_artifacts cutover-rehearsal --report-dir "$(CUTOVER_REPORT_DIR)" --environment "$(CUTOVER_ENVIRONMENT)" --release-sha "$(RELEASE_SHA)" --run-id "$(CUTOVER_RUN_ID)" --qa-owner "$(QA_OWNER)" --backend-owner "$(BACKEND_OWNER)" --on-call-reviewer "$(ON_CALL_REVIEWER)"

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

ops-backup-baseline:
	./ops/bin/backup-baseline.sh

ops-restore-baseline:
	@test -n "$(BACKUP_DIR)" || (echo "Usage: make ops-restore-baseline BACKUP_DIR=.local/backups/<timestamp>" && exit 1)
	BACKUP_DIR="$(BACKUP_DIR)" ./ops/bin/restore-baseline.sh