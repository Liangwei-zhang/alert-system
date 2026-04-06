# Target Topology

## Current Target

目前明確的生產部署目標形態是：

- 單台 VM 或單節點主機
- `docker compose` 編排
- PostgreSQL、PgBouncer、Redis、Kafka、ClickHouse、MinIO 與應用容器同機或同網段部署
- Nginx 作為對外入口

這不是最終高可用拓撲，但已經足以把以下運維基線補齊：

- file-backed secrets
- service healthcheck 與依賴啟動順序
- real readiness probes
- runtime metrics / alerts
- backup / restore baseline
- load baseline 與 cutover rehearsal

## Service Roles

常駐服務：

- `public-api`
- `admin-api`
- `scheduler`
- `event-pipeline`
- `retention`
- `tradingagents-bridge`
- `nginx`

data plane 基礎設施：

- `postgres`
- `pgbouncer`
- `redis`
- `kafka`
- `clickhouse`
- `minio`

一次性 / 按需 batch jobs：

- `migrate`
- `kafka-setup`
- `minio-setup`
- `scanner`
- `market-data`
- `cold-storage`
- `backtest`
- `receipt-escalation`

## Why Compose Plus VM First

- 目前最大的風險不是編排能力不足，而是 data plane operability 與 cutover discipline 不夠完整
- 單機 baseline 更容易把故障域、備份恢復、運行指標與實際 worker 型態校準清楚
- 倉庫內多個 worker 本質上是 batch job，不適合在沒有明確調度策略前硬套成長駐 deployment

## Readiness And Runtime Expectations

- `/health/ready` 會探測 PostgreSQL、Redis、ClickHouse、object storage
- `/v1/admin/runtime/metrics` 會輸出 component status 與平台運行指標
- `/v1/admin/runtime/alerts` 提供 broker lag、PgBouncer waiting、Redis memory、ClickHouse / object storage 失敗率告警
- runtime 期望的常駐元件目前只包括 `scheduler`、`event-pipeline`、`retention`、`tradingagents-bridge`

## Exit Criteria Before Moving To K8s

只有在以下條件成立後，才值得把主部署面切到 Kubernetes：

- 真實 cutover rehearsal 有穩定報告與 rollback 證據
- 備份恢復流程已經演練並可在明確 RTO / RPO 內完成
- 需要多副本、高可用或滾動發布，而不是單機容量問題
- 日誌、指標、告警與 secret rotation 已有集中化需求
- batch job 調度模型已經穩定，不再依賴臨時 compose profile 手工觸發