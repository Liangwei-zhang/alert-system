# Kubernetes Baseline

這個目錄現在提供一套可評審、可落地的 K8s baseline，但它仍然不是目前的默認交付面。近期生產目標依然是 compose + VM；這裡的 manifests 主要用來補齊 HPA、Prometheus、Grafana 與多副本拓撲的交付缺口。

## 目錄

- `base/namespace.yaml`: 命名空間
- `base/configmap.yaml`: 非敏感 runtime 配置
- `base/workloads.yaml`: migrate Job、public/admin API、scheduler、event-pipeline、retention、tradingagents-bridge，以及 Ingress
- `base/batch-jobs.yaml`: market-data、scanner、receipt-escalation、cold-storage、backtest 的 CronJob 拓撲
- `base/observability.yaml`: HPA、ServiceMonitor、PrometheusRule、Grafana dashboard ConfigMap
- `base/kustomization.yaml`: Kustomize 入口
- `overlays/staging/`: staging namespace、ingress、data-plane endpoint 與縮容策略
- `overlays/production/`: production namespace、ingress、managed endpoint 與放量策略

## 使用方式

```bash
kubectl apply -k ops/k8s/base
kubectl apply -k ops/k8s/overlays/staging
kubectl apply -k ops/k8s/overlays/production
OUTPUT_DIR=ops/reports/k8s/manual ./ops/bin/k8s-validate.sh
```

若要驗證非 base 的 overlay，直接覆寫 `KUSTOMIZE_PATH`：

```bash
KUSTOMIZE_PATH=ops/k8s/overlays/staging OUTPUT_DIR=ops/reports/k8s/staging ./ops/bin/k8s-validate.sh
```

`ops/bin/k8s-validate.sh` 預設會使用一個已驗證可拉取的 `bitnami/kubectl` digest；如果你需要對齊別的 client 版本，也可以用 `KUBECTL_IMAGE=...` 覆寫。
render 完成後，script 會再用 pinned `kubeconform` image 做離線 schema validation，避免 `kubectl apply --dry-run=client` 在沒有 cluster 時仍去做 API discovery；同樣可以用 `KUBECONFORM_IMAGE=...` 覆寫。

cutover rehearsal 現在還會把當次量測出的 runtime threshold 轉成一套可審核的 report overlay：

```bash
make cutover-k8s-overlay CUTOVER_ENVIRONMENT=staging CUTOVER_REPORT_DIR=ops/reports/cutover/<UTC timestamp>
KUSTOMIZE_PATH=ops/reports/cutover/<UTC timestamp>/k8s/overlays/staging OUTPUT_DIR=ops/reports/cutover/<UTC timestamp>/k8s/validation ./ops/bin/k8s-validate.sh
```

該 overlay 會把 namespace、ingress host、runtime alert threshold 與可選 image ref 收斂成 `ops/reports/cutover/<UTC timestamp>/k8s/overlays/<environment>/`，作為 staging / canary review bundle。

這套 baseline 假設下列依賴由集群外部或平台層提供：

- PostgreSQL / PgBouncer
- Redis
- Kafka
- ClickHouse
- S3 / MinIO compatible object storage

## 需要事先準備的 Secret

- `stock-py-app-secrets`
	- `DATABASE_URL`
	- `PGBOUNCER_ADMIN_URL`
	- `SECRET_KEY`
	- `TRADE_LINK_SECRET`
	- `INTERNAL_SIDECAR_SECRET`
	- `CLICKHOUSE_USERNAME`
	- `CLICKHOUSE_PASSWORD`
	- `OBJECT_STORAGE_ACCESS_KEY_ID`
	- `OBJECT_STORAGE_SECRET_ACCESS_KEY`
- `stock-py-monitoring-secret`
	- `publicMonitoringBearer`
	- `adminMetricsBearer`

## Batch 與 On-Demand 拓撲

- 週期性 batch worker 現在固定落在 `CronJob`，不再假設外部 VM crontab。
- 需要臨時重跑時，直接從 CronJob 派生一次性 Job：`kubectl create job --from=cronjob/scanner-batch scanner-batch-manual-<ts>`。
- always-on worker 仍維持 Deployment：`event-pipeline`、`retention`、`tradingagents-bridge`。

## 邊界與取捨

- 這裡不再把 batch worker 留給外部調度，改以 repo 內 manifests 定稿；真正的 stateful infra 依然交給平台層。
- `postgres` / `redis` / `kafka` / `clickhouse` / `minio` 沒有直接放進 repo manifests，避免在應用倉庫裡維護 stateful infra。
- admin metrics scrape 仍需額外 provision 一個專用 bearer token；public monitoring 則走新的 `/api/monitoring/metrics` 兼容路由。
- admin `/metrics?format=prometheus` 現在除了 HTTP counter/histogram，也會導出 broker lag、PgBouncer waiting clients、Redis memory、ClickHouse write failure rate、object storage archive failure rate，讓 `PrometheusRule` 與 cutover-generated overlay 使用同一批 gauge 名稱。