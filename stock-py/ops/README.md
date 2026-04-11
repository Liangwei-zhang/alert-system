# Deployment Scaffold

這一套部署檔已從單純的開發 / staging 骨架，補到可作為單機 production baseline 的形態：PostgreSQL、PgBouncer、Redis、Kafka、ClickHouse、MinIO、public/admin API、scheduler、event-pipeline、retention、tradingagents-bridge、Nginx，以及 profile 化的 batch jobs。

## 目標形態

- 近期生產目標：`docker compose + VM` 單機部署基線
- 當前不把 Kubernetes 當作近期默認交付面
- K8s 方向已補到 repo 內可評審 baseline，包含 batch CronJob 與離線 render/schema validation；是否切成主交付面仍取決於真實 HA / rollout 需求

這個決策是為了先把 secrets、healthcheck、啟動順序、備份恢復、運維指標、DLQ/replay 與 cutover rehearsal 做扎實，再決定是否把 K8s 提升為默認交付面。

## 啟動方式

最短入口：

```bash
make ops-stack-up
```

等價 compose 命令：

```bash
docker compose -f ops/docker-compose.yml up -d --build
```

batch jobs 不會默認常駐啟動。要手動跑它們時，使用 `jobs` profile：

```bash
docker compose -f ops/docker-compose.yml --profile jobs run --rm scanner
docker compose -f ops/docker-compose.yml --profile jobs run --rm cold-storage
```

Nginx 會暴露在 `http://localhost:8080`：

- `GET /health` 走 public API
- `GET /v1/admin/*` 走 admin API
- `GET /admin/docs` / `GET /admin/redoc` 走 admin API 文件

## Secrets 管理

- Compose 預設讀 `ops/secrets/dev/`
- 可透過 `OPS_SECRET_DIR` 切換到 `ops/secrets/local/` 或 `ops/secrets/production/`
- app 容器會直接讀取 `*_FILE`，避免把敏感值寫回 plain env vars

範例：

```bash
OPS_SECRET_DIR=./secrets/production docker compose -f ops/docker-compose.yml up -d
```

## Data Plane 設定

- ClickHouse：`ANALYTICS_BACKEND=clickhouse`
- MinIO / S3 相容物件儲存：`OBJECT_STORAGE_BACKEND=s3`
- 本地開發仍可維持 `EVENT_BROKER_BACKEND=redis`
- compose baseline 預設切到 `EVENT_BROKER_BACKEND=kafka`，並加上 topic bootstrap，不再依賴 auto-create topic
- PostgreSQL 連線預設走 PgBouncer transaction pooling，migration 服務仍直連 PostgreSQL，避免 DDL 走代理池

## 連線與容量策略

- app 容器的 `DATABASE_URL_FILE` 預設指向走 `pgbouncer:6432` 的 DSN，並帶上 `prepared_statement_cache_size=0`，避免 asyncpg 在 transaction pooling 下的 prepared statement 問題
- app 容器同時會為 asyncpg 打開 `statement_cache_size=0` 與 unique `prepared_statement_name_func`，避免 transaction pooling 下的 prepared statement 名稱衝突
- app 端同時設 `DATABASE_POOL_MODE=pgbouncer`，`infra/db/session.py` 會切到 `NullPool`，避免 PgBouncer 前面再疊一層大型應用內連線池
- Redis 保留 AOF，但加入明確的記憶體上限與淘汰策略
- Redis 淘汰策略預設不是 `allkeys-lru`，而是 `volatile-ttl`，因為這個倉庫同時把 Redis 用在 Streams、runtime registry、lock 與快取；不應該讓事件流或協調鍵被全域 LRU 淘汰
- Kafka 現在補了 healthcheck 與 topic bootstrap；仍然是單節點 KRaft baseline，不是最終 HA 拓撲
- ClickHouse 在 HTTP backend 自動建表時會帶上 `CLICKHOUSE_TABLE_TTL_DAYS`
- MinIO 會在 bucket bootstrap 時導入 `analytics-archive/` 與 `retention-archive/` 的 lifecycle 規則

可以透過 `.env` 或 shell 覆蓋這兩個 compose 變量：

```bash
REDIS_MAXMEMORY=1gb
REDIS_MAXMEMORY_POLICY=volatile-ttl
```

## Runtime 監控與告警出口

admin runtime route 現在除了 component health 之外，還會輸出：

- broker lag
- PgBouncer active / waiting clients
- Redis memory utilization
- ClickHouse write failure rate（近窗口）
- object storage archive failure rate（近窗口）

告警出口：

- `GET /v1/admin/runtime/alerts`
- `GET /metrics?format=prometheus`（admin API）現在也會導出同一批 runtime/platform gauges，供 PrometheusRule 與 K8s ServiceMonitor 直接使用

## 備份與恢復

基線策略是：

- PostgreSQL 是權威資料源，做 logical dump
- MinIO archive / report bucket 做 mirror 備份
- Kafka / ClickHouse 視為可重建 data plane，不當作權威資料源

入口：

```bash
make ops-backup-baseline
make ops-restore-baseline BACKUP_DIR=.local/backups/<UTC timestamp>
```

更完整步驟見 `ops/runbooks/backup-restore.md`。

## 真實 Data Plane 演練

用目前這套 PgBouncer + Kafka + ClickHouse + MinIO baseline 做 load / cutover rehearsal：

```bash
make ops-compose-load-baseline
make ops-compose-cutover-rehearsal
```

這兩個入口會把 compose `ps` / logs 與既有 load / cutover 報告工具鏈串起來。

`ops/bin/compose-load-baseline.sh` 現在除了 Locust 原始報表外，還會先自動 bootstrap disposable session / trade fixture，並寫入 `ops/reports/load/<UTC timestamp>/fixtures.env`、`fixtures.json` 與 `evidence/load-evidence-summary.json`。
compose baseline 也會自動設定本地 `INTERNAL_SIDECAR_SECRET`，並把同一個 token 傳給 public monitoring metrics scrape，避免 evidence capture 被 `/api/monitoring/metrics` 鑑權擋下。
`ops/bin/compose-cutover-rehearsal.sh` 會自動 bootstrap admin runtime token、抓 public health 與 admin runtime metrics / alerts、寫入 `ops/reports/cutover/<UTC timestamp>/evidence/cutover-validation.json`，再輸出 `runtime-alert-thresholds.env` / `.json`、`k8s/overlays/<environment>/summary.json` 與 `k8s/validation/summary.json`。

若要跑真實 `staging` / `canary` 驗證，先複製 `ops/reports/cutover/real-cutover.env.template` 到私有 env 檔並填入真實值，再執行：

```bash
make ops-real-cutover-validation CUTOVER_ENV_FILE=/absolute/path/to/real-cutover.env
```

若只想先推進 K8s/runtime lane，不等 load fixtures，可直接用：

```bash
make ops-real-k8s-runtime-validation CUTOVER_ENV_FILE=/absolute/path/to/real-cutover.env
```

這個入口會串起 real load baseline、cutover evidence、shadow-read、dual-write、rollback verification、runtime threshold calibration、K8s overlay validation，以及可選的 live `kubectl diff` / `apply` / `rollout undo`。
模板預設只開 read-only 路徑：load baseline、cutover evidence、shadow-read、offline K8s overlay/validation、以及可選的 live `kubectl diff`。`RUN_DUAL_WRITE`、`RUN_ROLLBACK_VERIFY`、`RUN_K8S_APPLY`、`RUN_K8S_ROLLBACK` 都需要顯式改成 `true` 才會執行。
如果真實 load fixtures / token 還沒就緒，但你已經有 admin runtime token 與 cluster context，可以先把 `RUN_LOAD_BASELINE=false`、`RUN_SHADOW_READ=false`，先推進 runtime 指標抓取、threshold calibration、overlay render、offline validation，以及 live `kubectl diff` 這條 K8s/runtime lane。
注意：`load-bootstrap-fixtures` / `cutover-bootstrap-fixtures` 只適用於本地 compose rehearsal，因為它們會直連本地資料庫建立 disposable fixtures；真實環境必須由外部預先提供可用的測試 token、trade fixture 與備份目錄。
真實環境所需的分階段輸入清單整理在 `ops/reports/cutover/real-env-required-inputs.md`。

若要單獨重跑 K8s handoff 資產，可以直接執行：

```bash
make cutover-k8s-overlay CUTOVER_ENVIRONMENT=staging CUTOVER_REPORT_DIR=ops/reports/cutover/<UTC timestamp>
make ops-k8s-validate K8S_KUSTOMIZE_PATH=ops/reports/cutover/<UTC timestamp>/k8s/overlays/staging K8S_VALIDATION_DIR=ops/reports/cutover/<UTC timestamp>/k8s/validation
```

事件数据面现在也补上了 dead-letter / replay 入口：

```bash
python -m infra.events.outbox stats
python -m infra.events.outbox replay-dead-letter --limit 50
```

## 常見命令

```bash
docker compose -f ops/docker-compose.yml ps
docker compose -f ops/docker-compose.yml logs -f pgbouncer redis kafka public-api admin-api event-pipeline retention tradingagents-bridge
docker compose -f ops/docker-compose.yml --profile jobs run --rm scanner
docker compose -f ops/docker-compose.yml down -v
```

## 參考文檔

- `ops/runbooks/backup-restore.md`
- `ops/runbooks/qa-cutover-checklist.md`
- `ops/TARGET_TOPOLOGY.md`
- `ops/k8s/README.md`

另外，repo 現在也補上兩份舊式 VM baseline helper：

- `ops/ecosystem.config.js`
- `ops/postgresql.conf.tuning`