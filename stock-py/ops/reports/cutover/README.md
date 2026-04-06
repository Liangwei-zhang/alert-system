# Cutover Reports

Store canary, rollback rehearsal, and post-cutover review artifacts here.

Recommended layout:

```text
ops/reports/cutover/
  20260405T020000Z/
    canary-rollback-rehearsal.md
    openapi/
      public_api_openapi_manifest.json
      admin_api_openapi_manifest.json
      openapi-diff.md
    screenshots/
    logs/
```

Use `canary-rollback-rehearsal-template.md` as the starting point for each rehearsal or real cutover record.

`make cutover-report-init` creates the timestamped report directory, a prefilled `canary-rollback-rehearsal.md`, and empty `screenshots/` plus `logs/` folders.
`make cutover-openapi-diff` writes the current OpenAPI manifests plus a markdown diff summary under the run's `openapi/` subdirectory.