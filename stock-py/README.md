# stock-py

股票訂閱與預警系統 - Python 重構版

## 三端架構

### 1. 管理端 (Admin) - 用戶/推送/治理
- 用戶管理 (創建/編輯/刪除/權限)
- 訂閱管理 (計劃/狀態/過期)
- 推送管理 (設備/統計/手動推送)
- 項目治理 (任務/回測/分發/審計)

### 2. 桌面端 (Platform) - 股票/算法/預警
- 股票監控 (實時報價/監控列表/搜索)
- 核心算法 (信號生成/策略引擎/回測/Market Regime)
- 預警系統 (預警觸發/確認/分發)
- 持倉管理 (持倉展示/交易記錄/P&L)

### 3. 訂閱端 (Subscriber) - 客戶/預警/資料
- 認證 (登入/註冊/驗證碼)
- 資料輸入 (關注股票/持有股票/現金)
- 接收預警 (站內/WebPush/郵件)
- 數據展示 (總資產/持倉明細/現金)

## 技術棧

- **後端**: FastAPI (async/await)
- **數據庫**: PostgreSQL (asyncpg) + PgBouncer transaction pooling
- **緩存**: Redis
- **調度**: APScheduler + dedicated async workers
- **事件**: Durable DB outbox + 可切換 Redis Streams / Kafka broker + dispatcher workers
- **HTTP 客戶端**: httpx

## 支持 100萬日活

- ✅ FastAPI (async) - 高性能
- ✅ PostgreSQL + PgBouncer 可切換連線治理
- ✅ Redis 緩存/限流/發布訂閱
- ✅ Worker/排程切面已拆出
- ✅ Outbox/EventBus 事件鏈路已接通
- ✅ WebPush 瀏覽器推送
- ✅ Data-plane 骨架已支援 Kafka / ClickHouse / S3-compatible backend 切換

## 當前入口

- **Python**: 3.13
- **API**: `apps/public_api/main.py`、`apps/admin_api/main.py`
- **排程**: `apps/scheduler/main.py`
- **Workers**: `apps/workers/*`

## 安裝

```bash
python3.13 -m pip install -r requirements.txt
cp .env.example .env
# 編輯 .env 配置數據庫和 Redis

# 執行 Alembic migration
alembic upgrade head

# 運行新 public API
python3.13 -m uvicorn apps.public_api.main:app --reload --host 0.0.0.0 --port 8000

# 運行新 admin API
python3.13 -m uvicorn apps.admin_api.main:app --reload --host 0.0.0.0 --port 8001

# 運行 scheduler
python3.13 -m apps.scheduler.main
```

也可以直接用 Makefile：

```bash
make install
make migrate
make format
make test
make run-public-api
```

## QA 驗證

```bash
# formatter / import order / style gate
make lint

# contract + e2e smoke baseline
make test-qa

# full unit + contract + e2e + load import baseline
make qa-ci

# 驗證 load scaffolding 可 import / compile
make test-load-import

# 查看 Locust CLI 與 scenario 是否可載入
make load-help

# 預先建立本次 baseline 的報告目錄與 summary stub
RELEASE_SHA=$(git rev-parse --short HEAD) \
QA_OWNER=qa@example.com \
BACKEND_OWNER=backend@example.com \
make load-report-init

# 實際跑 staging baseline（需要 disposable fixture）
LOAD_TEST_HOST=https://staging.example.com \
LOAD_TEST_ACCESS_TOKEN=... \
LOAD_TEST_REFRESH_TOKEN=... \
LOAD_TEST_TRADE_ID=trade-123 \
LOAD_TEST_TRADE_TOKEN=token-123 \
make load-baseline
```

`make load-baseline` 會先檢查必要環境變量，缺少 baseline 參數時直接失敗，不會默默跳過主要 scenario。
`make load-report-init` 會先在 `ops/reports/load/<UTC timestamp>/baseline-summary.md` 建立預填 metadata 的 summary stub；如果該次 run 已有人手工補充內容，這個命令不會覆蓋既有檔案。

建立 cutover rehearsal 記錄可以用：

```bash
RELEASE_SHA=$(git rev-parse --short HEAD) \
QA_OWNER=qa@example.com \
BACKEND_OWNER=backend@example.com \
ON_CALL_REVIEWER=oncall@example.com \
make cutover-report-init

# 導出目前 public/admin OpenAPI manifest，並和基線快照做 diff
RELEASE_SHA=$(git rev-parse --short HEAD) \
OPENAPI_BASELINE_DIR=tests/contract/snapshots \
make cutover-openapi-diff
```

這會建立 `ops/reports/cutover/<UTC timestamp>/canary-rollback-rehearsal.md`，並順手建立 `screenshots/` 與 `logs/` 目錄。
`make cutover-openapi-diff` 會在同一個 cutover 目錄下建立 `openapi/`，寫出目前的 public/admin manifest，以及 `openapi-diff.md` 摘要；如果你手邊有上一版 release artifact，也可以把 `OPENAPI_BASELINE_DIR` 指向那個目錄，而不是使用 repo 內的 contract snapshot。

GitHub Actions 現在會在 Python 3.13 上先跑 `make lint`，再跑 `make qa-ci`。

Locust 報告會自動輸出到 `ops/reports/load/<UTC timestamp>/`，包含：

- `baseline_stats.csv`
- `baseline_stats_history.csv`
- `baseline_failures.csv`
- `baseline.html`

如果要自定義輸出位置，可以覆寫 `LOAD_REPORT_PREFIX`：

```bash
LOAD_REPORT_PREFIX=ops/reports/load/staging-smoke/baseline make load-baseline
```

倉庫也提供 [`.github/workflows/qa.yml`](.github/workflows/qa.yml) 在 Python 3.13 上自動執行 unit、contract、e2e 與 load import 驗證。

## API 文檔

啟動後訪問: http://localhost:8000/docs

## 已遷移的新架構切面

- `apps/scheduler/main.py`: APScheduler 任務註冊中心，負責 heartbeat、event relay/dispatch、TradingAgents polling、market-data、scanner、retention、push/email dispatch、receipt escalation、backtest、cold storage 等週期任務
- `apps/public_api/routers/sidecars.py`: 補上 `/api/yahoo/{symbol}`、`/api/binance/{symbol}`、`/alerts`、`/api/telegram` sidecar surface，並以 internal sidecar secret 保護內部代理 / relay / bridge 路由
- `apps/workers/event_pipeline/worker.py`: 將 transaction 內持久化的 `event_outbox` relay 到可切換的 Redis Streams / Kafka broker，並由 dispatcher worker 觸發既有 subscriber 鏈路
- `apps/admin_api/routers/analytics.py`: 管理端 analytics read-model API，提供 overview、distribution、strategy health、TradingAgents 指標
- `apps/workers/analytics_sink/worker.py`: analytics sink subscriber 實作，透過 event-pipeline dispatcher 觸發下沉到 analytics storage
- `apps/workers/cold_storage/worker.py`: 將過舊 analytics partition 匯出到 object storage
- `infra/analytics/clickhouse_client.py`: 支援本地 JSONL facade 與真 ClickHouse HTTP backend，方便在本地與部署環境間切換
- `infra/storage/object_storage.py`: 支援本地 filesystem 與 S3/MinIO 相容 backend

## 容器化部署

倉庫現在提供以 `docker compose` 為核心的部署 scaffold，位於 `ops/docker-compose.yml`，會拉起：

- PostgreSQL
- PgBouncer
- Redis
- Kafka
- ClickHouse
- MinIO
- public/admin API
- scheduler、event-pipeline、retention、tradingagents-bridge 等常駐服務
- `jobs` profile 下的 batch workers（cold-storage、scanner、market-data、backtest、receipt-escalation）
- Nginx edge proxy

最短啟動流程：

```bash
make ops-stack-up
```

如果要直接使用 compose：

```bash
docker compose -f ops/docker-compose.yml up -d --build
```

這套 baseline 已補上：

- file-backed secrets 與 `ops/secrets/dev/` 開發預設
- PgBouncer / Kafka / ClickHouse / MinIO healthcheck
- migrate、topic bootstrap、bucket bootstrap 的啟動順序
- ClickHouse table TTL 與 MinIO archive lifecycle
- batch job 與 always-on service 分層
- 基於真實 data plane 的 load / cutover / backup / restore 腳本入口

常用入口：

```bash
make ops-compose-load-baseline
make ops-compose-cutover-rehearsal
make ops-backup-baseline
make ops-restore-baseline BACKUP_DIR=.local/backups/<UTC timestamp>
```

目前 compose 也為 Redis 補上了明確的容量策略，預設採 `volatile-ttl` 而不是 `allkeys-lru`，因為這個倉庫會把 Redis 同時用在快取、runtime registry、分散式 lock 與 broker 配套協調鍵；全域 LRU 會對事件與協調鍵帶來不必要的風險。

Admin runtime 監控除了 component health 之外，現在也會輸出 broker lag、PgBouncer waiting clients、Redis 記憶體水位、ClickHouse 寫入失敗率、object storage archive 失敗率，並提供 `/v1/admin/runtime/alerts` 作為告警出口。

詳細說明見 `ops/README.md`。

## 項目結構

```
stock-py/
├── apps/
│   ├── public_api/          # Public API 入口與路由
│   ├── admin_api/           # Admin API 入口與路由
│   ├── scheduler/           # 排程入口
│   └── workers/             # 事件/數據/通知 workers
├── domains/                 # 領域服務、schema、repository
├── infra/                   # 基礎設施層: db、events、security、analytics
├── alembic/                 # DB migration
├── tests/                   # unit / contract / e2e / load
└── docs/                    # 設計與遷移文檔
```

## License

Apache 2.0