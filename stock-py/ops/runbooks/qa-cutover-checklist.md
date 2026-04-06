# QA Cutover Checklist

## Scope

- Environment: `staging` / `canary` / `production`
- Release SHA:
- QA owner:
- Backend owner:
- Rollback approver:

## 1. Deployment Gate

- [ ] Target image / package version is pinned and matches the release SHA.
- [ ] `OPS_SECRET_DIR` / secret set has been reviewed for DB, Redis, webhook, mail, MinIO, and internal API keys.
- [ ] Worker, scheduler, public API, and admin API rollout order is documented.
- [ ] Confirm the target shape is the current compose + VM baseline, not an ad-hoc K8s manifest mix.
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

- [ ] Enable shadow reads for account dashboard and profile endpoints.
- [ ] Enable shadow reads for notification list and push-device queries.
- [ ] Enable shadow reads for trade info endpoints.
- [ ] Capture latency and payload parity samples for at least 15 minutes.
- [ ] Document mismatches before canary percentage is raised.

## 5. Dual-Write Verification

- [ ] Subscription state writes are mirrored and sampled for parity.
- [ ] Notification receipts and ack state are mirrored and sampled for parity.
- [ ] Trade confirmations / ignores are mirrored and sampled for parity.
- [ ] TradingAgents analysis submissions and terminal results are mirrored and sampled for parity.
- [ ] Any write mismatch has an owner, ticket, and containment decision.

## 6. Load Test Gate

- [ ] Locust dependency is installed from `requirements.txt`.
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
- [ ] Revert application deployment and verify health endpoints.
- [ ] Verify the latest PostgreSQL dump and MinIO mirror backup are readable before proceeding with data restore.
- [ ] Re-run smoke checks for auth, dashboard, notifications, trades, scanner ingest, and TradingAgents webhook.
- [ ] Reconcile delayed TradingAgents jobs and notification outbox backlog.
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

### First 24 Hours

- [ ] Subscription churn anomalies
- [ ] Portfolio / watchlist parity spot checks
- [ ] Backlog growth in outbox, webhook, and scheduled task queues
- [ ] On-call incident summary and follow-up ticket creation