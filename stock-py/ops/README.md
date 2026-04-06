# Deployment Scaffold

這一套部署檔已從單純的開發 / staging 骨架，補到可作為單機 production baseline 的形態：PostgreSQL、PgBouncer、Redis、Kafka、ClickHouse、MinIO、public/admin API、scheduler、event-pipeline、retention、tradingagents-bridge、Nginx，以及 profile 化的 batch jobs。

## 目標形態

- 近期生產目標：`docker compose + VM` 單機部署基線
- 當前不把 Kubernetes 當作近期默認交付面
- K8s 方向保留在 `ops/k8s/README.md`，等高可用、滾動發布、集中式日誌與資源配額要求真正成為主需求時再切換

這個決策是為了先把 secrets、healthcheck、啟動順序、備份恢復、運維指標與 cutover rehearsal 做扎實，避免在 K8s 和 VM 之間來回重做。

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