# Load Reports

Store generated Locust baseline artifacts here.

Recommended layout:

```text
ops/reports/load/
  20260404T201500Z/
    baseline_stats.csv
    baseline_stats_history.csv
    baseline_failures.csv
    baseline.html
```

`make load-baseline` writes to `ops/reports/load/<UTC timestamp>/baseline*` by default.

Use `make load-report-init` first if you want a prefilled `baseline-summary.md` stub next to the raw Locust artifacts before the run starts.

Do not commit generated CSV / HTML artifacts unless the change is explicitly meant to preserve a reviewed baseline snapshot.