# Real Environment Required Inputs

Use this file as the handoff checklist before running real staging or canary validation.

## Lane 1: K8s / Runtime Only

Use this when load fixtures are not ready yet.

Command:

```bash
make ops-real-k8s-runtime-validation CUTOVER_ENV_FILE=/absolute/path/to/real-cutover.env
```

Required values:

- `RELEASE_SHA`
- `QA_OWNER`
- `BACKEND_OWNER`
- `ON_CALL_REVIEWER`
- `STACK_PUBLIC_HEALTH_URL`
- `ADMIN_RUNTIME_URL`
- `ADMIN_RUNTIME_TOKEN`

Required for live cluster checks:

- `KUBECTL_CONTEXT` or `KUBECONFIG`
- `K8S_NAMESPACE`
- `K8S_INGRESS_HOST`
- `K8S_RELEASE_IMAGE` when validating a concrete image rollout rather than just runtime thresholds

Optional but commonly needed:

- `RUN_K8S_DIFF=true`
- `RUN_K8S_APPLY=true` only after rollout approval
- `RUN_K8S_ROLLBACK=true` only after rollback approval

## Lane 2: Full Read-Only Cutover

Use this when you can run real load and shadow-read, but not write-path or restore-path drills.

Command:

```bash
make ops-real-cutover-validation CUTOVER_ENV_FILE=/absolute/path/to/real-cutover.env
```

Additional required values beyond Lane 1:

- `LOAD_TEST_HOST`
- `LOAD_TEST_ACCESS_TOKEN`
- `LOAD_TEST_REFRESH_TOKEN`
- `LOAD_TEST_TRADE_ID`
- `LOAD_TEST_TRADE_TOKEN`
- `LEGACY_BASE_URL`
- `SHADOW_READ_SHADOW_BASE_URL`

## Lane 3: Full Destructive Validation

Enable this only after disposable fixtures, backup evidence, and rollback approval exist.

Additional required values beyond Lane 2:

- `PRIMARY_SUBSCRIPTION_START_URL`
- `PRIMARY_ACCOUNT_PROFILE_URL`
- `PRIMARY_NOTIFICATION_ACK_URL`
- `PRIMARY_NOTIFICATION_READBACK_URL`
- `PRIMARY_TRADE_APP_CONFIRM_URL`
- `PRIMARY_TRADE_APP_IGNORE_URL`
- `PRIMARY_TRADE_APP_ADJUST_URL`
- `PRIMARY_TRADE_READBACK_URL`
- `PRIMARY_TRADINGAGENTS_SUBMIT_URL`
- `PRIMARY_TRADINGAGENTS_ANALYSIS_URL`
- `PRIMARY_TRADINGAGENTS_TERMINAL_URL`
- `DUAL_WRITE_TRADINGAGENTS_REQUEST_ID`
- `DUAL_WRITE_TRADINGAGENTS_JOB_ID`
- `DUAL_WRITE_WEBHOOK_SIGNATURE`
- `BACKUP_DIR`

Required toggles:

- `RUN_DUAL_WRITE=true`
- `DUAL_WRITE_ALLOW_MUTATIONS=true`
- `RUN_ROLLBACK_VERIFY=true`

## Non-Repo Blockers

These cannot be generated from this repository and must come from the real environment owner:

- Disposable load user access token and refresh token
- Disposable trade fixture id and public token
- Legacy base URL for parity sampling
- Primary write/readback URLs for dual-write scenarios
- Readable PostgreSQL dump plus MinIO mirror path for rollback verification
- Real cluster context or kubeconfig for live `kubectl diff/apply/undo`