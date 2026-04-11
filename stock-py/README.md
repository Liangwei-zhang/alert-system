# stock-py

股票訂閱與預警系統 - 獨立 Python 主系統

## 系統定位

- `stock-py` 是後續獨立運行的主系統，資料、部署與運維邊界以本倉庫為準。
- 預設基線使用獨立 PostgreSQL / Redis / ClickHouse / object storage 命名，不再沿用舊 `stock` 的默認資料庫識別。
- subscriber / admin / platform 三端 UI 屬於 `stock-py` 正式產品範圍，現在由 Python 直接提供 `/app`、`/platform`、`/admin` 三個純 HTML 入口，不再依賴舊 `stock` 倉庫或 Node build pipeline。
- 三端的產品邊界應按「訂閱端 = 用戶資料輸入與接收通知」「桌面端 = 策略核心」「管理端 = 用戶/推送/治理/監控」理解，而不是按目前某些高權限 API 暫時掛在哪個服務下理解。

## 三端架構

### 1. 桌面端 (Platform) - 策略核心
- 候選標的池、觀察列表、持倉與交易執行
- 買入預警策略與退出策略的選擇、調參與迭代
- 歷史回測、勝率、排名與策略效果驗證
- 桌面策略駕駛艙與內部高權限策略接口的產品歸屬

#### 桌面端需求對齊（2026-04）
- 已對齊：候選標的搜索、觀察池 / 持倉、入場 / 退出參數維護、交易執行閉環，現在都已可由 `/platform` 或 `/next/platform` 承接，底層分別對應 `search`、`watchlist`、`portfolio`、`trades` 等 public API。
- 已對齊：`/next/platform` 的信息架構已按策略核心重排為候選標的、策略組合、參數維護、交易執行與內部策略接口台，與先前確認的產品邊界一致。
- 過渡中：`backtests`、`scanner`、`signal-stats`、`analytics`、`tradingagents` 這組高權限策略能力，技術上仍經 `admin_api` 的 `/v1/admin/*` 暴露，但產品上已視為桌面端策略核心的一部分。
- 已對齊：`/next/platform` 已內嵌 `admin-auth` 驗證入口，桌面端可直接用 `/v1/admin-auth/send-code`、`/v1/admin-auth/verify`、`/v1/admin-auth/refresh` 建立高權限策略 session；僅生成簽名 JWT 而不落 session 時，`admin_api` 仍會回 `session_revoked`。
- 開發優先級：桌面端後續應以 `/next/platform` 作為主開發面，持續把回測、勝率、排名、策略觀測與實驗能力往這個策略工作台收口，而不是再擴散到管理端。

### 2. 管理端 (Admin) - 用戶/推送/治理
- 用戶生命週期與訂閱狀態管理
- 推送設備、手動消息、發件箱、回執與運營任務
- 操作員權限、審計、運行監控、告警與驗收證據
- 對平台策略服務的內部觀測與應急操作，但不是策略產品中心

### 3. 訂閱端 (Subscriber) - 客戶/通知/資料
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
- **HTML UI routes**: `apps/public_api/routers/ui.py`（`/app`、`/platform`、`/admin` 三端純 HTML 入口）

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
make run-admin-api
```

## 純 HTML UI 路由

`stock-py` 現在直接由 Python 提供三端 HTML shell，不需要 `npm install` 或前端編譯步驟。

```bash
make run-public-api
make run-admin-api
```

如果你是走 compose / nginx，直接開同一個 host：

- `/app`：subscriber 郵箱驗證碼登入、本地離線草稿、訂閱股票 / 已持倉股票 / 現金錄入，以及單次 `开始订阅` 同步
- `/platform`：桌面策略核心入口；當前已承接 symbol search、shared watchlist / portfolio、trade lookup 與 app trade execution，買入預警、退出策略、回測與勝率能力也應由同一產品面承接
- `/admin`：內部運營治理入口；主責 admin 登入、operators、manual distribution、task center、users、audit、runtime 指標與告警，`scanner` / `backtests` / `analytics` 等高權限頁面屬於對平台核心的內部觀測與治理支援

注意：目前 `backtests`、`scanner`、`signal-stats`、`analytics` 等高權限策略接口在技術上仍掛在 `admin_api` 下，但這不代表它們的產品歸屬屬於管理端；從產品邊界看，它們仍是桌面端策略核心的一部分。

如果你直接開 public API 而不是經過 nginx，也可以在 query string 預先指定 API base URL：

```bash
http://localhost:8000/app?admin_api_base_url=http://localhost:8001
http://localhost:8000/admin?admin_api_base_url=http://localhost:8001
```

`/admin` 現在已支持 active admin operator 的郵箱驗證碼登入；若你是在排查代理 / nginx / token 問題，也仍可手動貼上 bearer token 覆蓋當前 admin session。

## QA 驗證

```bash
# formatter / import order / style gate
make lint

# contract + e2e smoke baseline
make test-qa

# 平台桌面端 smoke：驗證平台頁/腳本標記、admin-auth verify/refresh/logout、只讀數據鏈路
make smoke-platform-workbench \
PLATFORM_SMOKE_PUBLIC_BASE_URL=http://127.0.0.1:8012 \
PLATFORM_SMOKE_ADMIN_BASE_URL=http://127.0.0.1:8011

# 平台桌面端交互 smoke：用前端真實 JS 鏈路驗證 send-code -> verify -> loadAll -> 首屏自動路由 -> reload restore -> logout
make smoke-platform-workbench-interaction \
PLATFORM_SMOKE_PUBLIC_BASE_URL=http://127.0.0.1:8012 \
PLATFORM_SMOKE_ADMIN_BASE_URL=http://127.0.0.1:8011

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

# baseline 完成後補抓 health / metrics evidence bundle
LOAD_TEST_HOST=https://staging.example.com \
LOAD_PUBLIC_METRICS_TOKEN=internal-monitoring-bearer \
make load-report-capture
```

`make load-baseline` 會先檢查必要環境變量，缺少 baseline 參數時直接失敗，不會默默跳過主要 scenario。
`make load-report-init` 會先在 `ops/reports/load/<UTC timestamp>/baseline-summary.md` 建立預填 metadata 的 summary stub；如果該次 run 已有人手工補充內容，這個命令不會覆蓋既有檔案。
`make load-bootstrap-fixtures` 會在本地 compose stack 上自動建立 disposable user session、admin runtime token 與 trade fixture，並把結果寫到 `ops/reports/load/<UTC timestamp>/fixtures.env`；`make ops-compose-load-baseline` 已經會自動串這一步。
如果 metrics scrape 走受保護的 `/api/monitoring/metrics`，`make load-report-capture` 也需要帶 `LOAD_PUBLIC_METRICS_TOKEN`；`make ops-compose-load-baseline` 會自動替本地 compose baseline 注入對應的 monitoring secret。

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

如果要把 public health、admin runtime metrics / alerts 一起沉澱到同一份 cutover evidence bundle，可以再跑：

```bash
STACK_PUBLIC_HEALTH_URL=https://staging.example.com/health \
ADMIN_RUNTIME_URL=https://admin.example.com \
ADMIN_RUNTIME_TOKEN=... \
make cutover-evidence-capture
```

如果要把 admin runtime metrics 進一步轉成一份可審核的 threshold 建議 env，可以再跑：

```bash
CUTOVER_REPORT_DIR=ops/reports/cutover/<UTC timestamp> \
make cutover-threshold-calibrate
```

`make ops-compose-cutover-rehearsal` 現在會自動完成 fixture/bootstrap、OpenAPI diff、evidence capture、threshold 建議輸出，以及 K8s baseline 的離線 render/schema validation。

GitHub Actions 現在會在 Python 3.13 上先跑 `make lint`，再跑 `make qa-ci`。

## 策略目標基準

如果你要驗證當前 ranking-aware live strategy 是否仍然達到這輪遷移的目標勝率，可以直接跑：

```bash
.venv/bin/python run_live_strategy_goal_benchmark.py
```

這個命令會使用 archive-backed `1d` universe，默認按最近 `365` 根 bar 切成 `275` 根訓練 + `90` 根測試，baseline 使用舊 heuristic selector，ranking 輸入則優先取最近一批正式 benchmark-backed rankings，並把以下門檻當成 quality gate：

- 新邏輯勝率 `>= 65.58%`
- 絕對提升 `>= 10.89` 個百分點
- 相對提升 `>= 19.92%`

如果你想把 ranking 輸入切回純 train-window proxy，而不是使用資料庫裡最近一批正式 rankings，可以改成：

```bash
.venv/bin/python run_live_strategy_goal_benchmark.py --ranking-source train_window
```

如果你想看固定 `rsi_proxy` 的對照，也可以顯式指定：

```bash
.venv/bin/python run_live_strategy_goal_benchmark.py --baseline rsi_proxy
```

目標未達標時腳本會返回非零 exit code；如果只想看報告不想阻斷流程，可以加 `--allow-goal-miss`。如需保存 JSON 報告，可再加 `--output ops/reports/backtest-goal/latest.json`。

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

- `apps/public_api/routers/ui.py` + `apps/public_api/ui_shell.py`: 由 FastAPI 直接輸出 `/app`、`/platform`、`/admin` 純 HTML 介面，透過瀏覽器直連 public/admin API
- `apps/scheduler/main.py`: APScheduler 任務註冊中心，負責 heartbeat、event relay/dispatch、TradingAgents polling、market-data、scanner、retention、push/email dispatch、receipt escalation、backtest、cold storage 等週期任務
- `apps/public_api/routers/sidecars.py`: 補上 `/api/yahoo/{symbol}`、`/api/binance/{symbol}`、`/alerts`、`/api/telegram` sidecar surface，並以 internal sidecar secret 保護內部代理 / relay / bridge 路由
- `apps/public_api/routers/monitoring.py`: 補上 legacy `/api/monitoring/stats`、`/api/monitoring/metrics`、`/api/monitoring/reset` 兼容路由，支援 bearer 或 internal sidecar secret 鑑權
- `apps/workers/event_pipeline/worker.py`: 將 transaction 內持久化的 `event_outbox` relay 到可切換的 Redis Streams / Kafka broker，並由 dispatcher worker 觸發既有 subscriber 鏈路
- `infra/events/outbox.py`: 補上 dead-letter / replay repository 與 CLI，支援 `python -m infra.events.outbox stats`、`python -m infra.events.outbox replay-dead-letter`
- `apps/admin_api/routers/analytics.py`: 內部高權限 analytics read-model API，提供 overview、distribution、strategy health、TradingAgents 指標，主要服務平台策略觀測與 admin 治理復核
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
- 本地 fixture bootstrap、runtime threshold calibration、K8s manifest 離線 render/schema validation 工具鏈
- `ops/ecosystem.config.js` 與 `ops/postgresql.conf.tuning` 這類 VM 補充文件
- `ops/k8s/base/` 下可評審且已附 batch CronJob 拓撲與離線 validation 的 K8s / HPA / Prometheus / Grafana baseline

常用入口：

```bash
make ops-compose-load-baseline
make ops-compose-cutover-rehearsal
make ops-backup-baseline
make ops-restore-baseline BACKUP_DIR=.local/backups/<UTC timestamp>
```

目前 compose 也為 Redis 補上了明確的容量策略，預設採 `volatile-ttl` 而不是 `allkeys-lru`，因為這個倉庫會把 Redis 同時用在快取、runtime registry、分散式 lock 與 broker 配套協調鍵；全域 LRU 會對事件與協調鍵帶來不必要的風險。

Admin runtime 監控除了 component health 之外，現在也會輸出 broker lag、PgBouncer waiting clients、Redis 記憶體水位、ClickHouse 寫入失敗率、object storage archive 失敗率，並提供 `/v1/admin/runtime/alerts` 作為告警出口。

Public API 也補回了 legacy `/api/monitoring/*` 相容面，並且 `GET /metrics?format=prometheus` / `GET /api/monitoring/metrics` 都可以輸出 Prometheus text format。

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
└── docs/                    # 設計與歷史遷移文檔
```

## License

Apache 2.0