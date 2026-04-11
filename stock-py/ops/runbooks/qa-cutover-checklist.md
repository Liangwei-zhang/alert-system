# QA Cutover Checklist

## Scope

- Environment: `staging` / `canary` / `production`
- Release SHA:
- QA owner:
- Backend owner:
- Rollback approver:

## 1. Deployment Gate

- [ ] For a real staging/canary run, copy `ops/reports/cutover/real-cutover.env.template` to a private env file and prefer `make ops-real-cutover-validation CUTOVER_ENV_FILE=...` so load, parity, rollback, and K8s evidence land under one report bundle.
- [ ] The real-env template defaults to read-only checks. Only enable `RUN_DUAL_WRITE`, `RUN_ROLLBACK_VERIFY`, `RUN_K8S_APPLY`, or `RUN_K8S_ROLLBACK` after the target env has disposable fixtures, backup evidence, and rollback approval.
- [ ] If the K8s/runtime lane can start before load fixtures are ready, set `RUN_LOAD_BASELINE=false` and `RUN_SHADOW_READ=false` so the wrapper only blocks on release metadata, admin runtime access, and cluster-side inputs.
- [ ] Prefer `make ops-real-k8s-runtime-validation CUTOVER_ENV_FILE=...` when only the runtime/K8s lane is unblocked; use `ops/reports/cutover/real-env-required-inputs.md` as the phase-by-phase input checklist.
- [ ] Target image / package version is pinned and matches the release SHA.
- [ ] `OPS_SECRET_DIR` / secret set has been reviewed for DB, Redis, webhook, mail, MinIO, and internal API keys.
- [ ] Worker, scheduler, public API, and admin API rollout order is documented.
- [ ] Confirm the target shape is the current compose + VM baseline, not an ad-hoc K8s manifest mix.
- [ ] If this rehearsal also prepares a K8s handoff bundle, run `make cutover-k8s-overlay ...` or `make ops-compose-cutover-rehearsal` first and review `ops/reports/cutover/<UTC timestamp>/k8s/overlays/<environment>/summary.json`.
- [ ] Verify the generated overlay namespace, ingress host, monitoring secret name, release image, and runtime threshold patch before any canary apply step.
- [ ] Feature flags for canary traffic, dual write, and webhook verification are explicitly recorded.

## 2. Migration Checks

- [ ] `alembic upgrade head` completes in the target environment.
- [ ] Schema drift check against production snapshot is clean.
- [ ] Seed data required for QA smoke users, watchlists, portfolios, notifications, and trade fixtures is present.
- [ ] TradingAgents and notification outbox tables show writable health after migration.

## 3. OpenAPI Diff Check

- [ ] Run `make cutover-openapi-diff RELEASE_SHA=... OPENAPI_BASELINE_DIR=...` to export the current public/admin manifests and produce a review summary.
- [ ] Review `ops/reports/cutover/<UTC timestamp>/openapi/openapi-diff.md` and attach it to the release record.
- [ ] Confirm the baseline directory points to the previous release artifact bundle or the reviewed snapshot source of truth.
- [ ] Any breaking change has explicit sign-off from the consuming team.

## 4. Shadow Read Check

- [ ] If using the real-env wrapper, ensure `LEGACY_BASE_URL` and `SHADOW_READ_SHADOW_BASE_URL` are filled in the private env file before execution.
- [ ] Review `ops/reports/cutover/<UTC timestamp>/shadow-read-scenarios.json` and fill the exact primary / shadow URLs plus any auth placeholders before sampling.
- [ ] Run `make cutover-shadow-read CUTOVER_REPORT_DIR=... SHADOW_READ_DURATION_SECONDS=900 SHADOW_READ_INTERVAL_SECONDS=30` to generate `shadow-read-summary.md` and `evidence/shadow-read-results.json`.
- [ ] Enable shadow reads for account dashboard and profile endpoints.
- [ ] Enable shadow reads for notification list and push-device queries.
- [ ] Enable shadow reads for trade info endpoints.
- [ ] Capture latency and payload parity samples for at least 15 minutes.
- [ ] Document mismatches before canary percentage is raised.
- [ ] Remember this command only captures HTTP parity evidence; the actual traffic mirroring / routing switch remains owned by deploy config or platform flags.

## 5. Dual-Write Verification

- [ ] If using the real-env wrapper, fill the primary write/readback URL variables plus TradingAgents request/job/signature values in the private env file and set `DUAL_WRITE_ALLOW_MUTATIONS=true`.
- [ ] Review `ops/reports/cutover/<UTC timestamp>/dual-write-scenarios.json` and fill the exact write / readback URLs plus disposable fixture IDs before running the write parity step.
- [ ] Run `make cutover-dual-write CUTOVER_REPORT_DIR=... DUAL_WRITE_ALLOW_MUTATIONS=true` to generate `dual-write-summary.md` and `evidence/dual-write-results.json`.
- [ ] Subscription state writes are mirrored and sampled for parity.
- [ ] Notification receipts and ack state are mirrored and sampled for parity.
- [ ] Trade confirmations / ignores are mirrored and sampled for parity.
- [ ] TradingAgents analysis submissions and terminal results are mirrored and sampled for parity.
- [ ] Any write mismatch has an owner, ticket, and containment decision.

## 6. Load Test Gate

- [ ] Locust dependency is installed from `requirements.txt`.
- [ ] For real env runs, do not use `make load-bootstrap-fixtures` or `make cutover-bootstrap-fixtures`; those commands seed disposable fixtures through the local DB and are only valid for compose rehearsal.
- [ ] Run `make load-report-init RELEASE_SHA=... QA_OWNER=... BACKEND_OWNER=...` to create the summary stub before the baseline starts.
- [ ] Prefer `make ops-compose-load-baseline` when validating the full PgBouncer + Kafka + ClickHouse + MinIO stack.
- [ ] If running Locust manually, point it at the compose stack or another non-production environment with the same data plane topology.
- [ ] Archive Locust CSV / HTML output under `ops/reports/load/<UTC timestamp>/` or attach an equivalent artifact bundle.
- [ ] Fill `ops/reports/load/<UTC timestamp>/baseline-summary.md` and store the reviewed summary next to the raw artifacts.
- [ ] `LOAD_TEST_ACCESS_TOKEN`, `LOAD_TEST_REFRESH_TOKEN`, `LOAD_TEST_TRADE_ID`, and `LOAD_TEST_TRADE_TOKEN` are populated with disposable fixtures.
- [ ] Trade mutations remain disabled unless using dedicated disposable trade fixtures.
- [ ] Baseline latency, error rate, and saturation metrics are attached to the release record.

## 7. Rollback Steps

- [ ] Freeze new canary expansion.
- [ ] Disable write-path feature flags and internal job submissions.
- [ ] Route traffic back to the previous stable deployment.
- [ ] If using the real-env wrapper, make sure `BACKUP_DIR` points to a readable PostgreSQL dump + MinIO mirror before enabling `RUN_ROLLBACK_VERIFY=true`.
- [ ] If using the generated K8s bundle, save the exact `kubectl diff -k` / `kubectl apply -k` / rollback command set alongside the report overlay path.
- [ ] Revert application deployment and verify health endpoints.
- [ ] Verify the latest PostgreSQL dump and MinIO mirror backup are readable before proceeding with data restore.
- [ ] Re-run smoke checks for auth, dashboard, notifications, trades, scanner ingest, and TradingAgents webhook.
- [ ] Reconcile delayed TradingAgents jobs and notification outbox backlog.
- [ ] Run `make cutover-rollback-verify CUTOVER_REPORT_DIR=... BACKUP_DIR=.local/backups/<UTC timestamp>` and attach the resulting `rollback-verification.md` evidence.
- [ ] Run `make cutover-report-init RELEASE_SHA=... QA_OWNER=... BACKEND_OWNER=... ON_CALL_REVIEWER=...` if the rehearsal record bundle has not been created yet.
- [ ] Save the rehearsal or real rollback notes under `ops/reports/cutover/<UTC timestamp>/` using `canary-rollback-rehearsal-template.md`.

## 8. Post-Cutover Monitoring

### First 30 Minutes

- [ ] Public API 5xx rate
- [ ] Admin API 5xx rate
- [ ] P95 latency for auth, dashboard, notifications, and trades
- [ ] Broker lag and retry volume
- [ ] PgBouncer waiting clients
- [ ] Redis memory utilization

### First 2 Hours

- [ ] TradingAgents completion / failure ratio
- [ ] Notification delivery success rate
- [ ] Scanner ingest acceptance / suppression ratio
- [ ] DB connection pool saturation and slow query count
- [ ] ClickHouse write failure rate
- [ ] Object storage archive failure rate
- [ ] PrometheusRule thresholds in the applied overlay still match the reviewed `runtime-alert-thresholds.env`

### First 24 Hours

- [ ] Subscription churn anomalies
- [ ] Portfolio / watchlist parity spot checks
- [ ] Backlog growth in outbox, webhook, and scheduled task queues
- [ ] On-call incident summary and follow-up ticket creation

## 9. Final Signoff

- [ ] Run `make cutover-signoff CUTOVER_REPORT_DIR=... SIGNOFF_LOAD_REPORT_DIR=ops/reports/load/<UTC timestamp> BACKUP_DIR=.local/backups/<UTC timestamp>`.
- [ ] If no real cluster rollout evidence exists, keep the resulting deployment posture at `handoff_baseline` or `compose_vm_baseline`; do not represent K8s as production cutover complete.
- [ ] Archive `cutover-signoff-summary.md` together with the reviewed load / cutover bundle.