# stock-py 當前系統架構

> 狀態（2026-04-06）：本文描述 `stock-py` 作為獨立主系統時，當前已落地的 API、worker、資料平面與運維邊界。`docs/python-migration/*` 僅保留為歷史遷移拆分參考，不再作為現行產品邊界定義。

## 0. 系統邊界

- `stock-py` 是後續獨立運行的主系統與部署單位，預設使用獨立資料庫、事件主題、analytics database 與 object storage bucket。
- `public_api`、`admin_api`、scheduler / workers 與 `ops/*` 的 load、cutover、backup、K8s 工具鏈共同構成目前的 authoritative backend / ops baseline。
- subscriber / admin / platform 三端 UI 已屬於 `stock-py` 產品邊界，現由 `apps/public_api/routers/ui.py` 直接輸出純 HTML 路由 `/app`、`/platform`、`/admin`。

## 0.1 三端產品邊界

- `platform` 是策略核心：候選標的、買入預警、退出策略、歷史回測、勝率/排名、策略驗證與交易執行都應從產品歸屬上算在平台端。
- `admin` 是運營治理面：用戶生命週期、推送與手動分發、操作員權限、審計、任務中心、運行監控、驗收與發布證據屬於管理端主責。
- `app` 是訂閱端：普通用戶登入、錄入 watchlist / portfolio / cash、接收通知、查看自身資產與同步狀態。
- 目前 `backtests`、`scanner`、`signal-stats`、`analytics`、`tradingagents` 等高權限策略接口在技術上仍掛在 `admin_api` 下，但它們主要是平台核心的內部控制面 / 觀測面，不應被解讀成管理端產品中心。

## 1. 對外服務面

### 1.1 Public API

**職責：**
- 用戶認證與 session 管理
- 帳戶 / 訂閱 / watchlist / portfolio / search
- notifications 與 trade workflow
- internal signal ingest 與 TradingAgents internal hooks
- health / metrics 對外暴露

**路由前綴：**
```text
/health
/metrics
/v1/auth/*
/v1/account/*
/v1/watchlist/*
/v1/portfolio/*
/v1/search/*
/v1/notifications/*
/v1/trades/*
/v1/internal/signals/*
/v1/internal/tradingagents/*
```

### 1.2 Admin API

**職責：**
- 用戶、訂閱、推送、操作員與審計治理
- runtime monitoring、tasks center、acceptance / release evidence
- anomalies、distribution manual command 與運營補償操作
- 提供平台核心所需的高權限內部策略觀測接口，例如 backtests / scanner / signal stats / analytics / TradingAgents
- admin auth / metrics / health

**路由前綴：**
```text
/health
/metrics
/v1/admin/acceptance/*
/v1/admin/anomalies/*
/v1/admin/analytics/*
/v1/admin/audit/*
/v1/admin/backtests/*
/v1/admin/distribution/*
/v1/admin/operators/*
/v1/admin/runtime/*
/v1/admin/scanner/*
/v1/admin/signal-stats/*
/v1/admin/tasks/*
/v1/admin/tradingagents/*
/v1/admin/users/*
```

### 1.3 Background Processes

目前倉庫中的長任務與批處理入口：

```text
apps/scheduler/main.py
apps/workers/scanner/worker.py
apps/workers/market_data/worker.py
apps/workers/backtest/worker.py
apps/workers/event_pipeline/worker.py
apps/workers/notification_orchestrator/worker.py
apps/workers/push_dispatch/worker.py
apps/workers/email_dispatch/worker.py
apps/workers/receipt_escalation/worker.py
apps/workers/retention/worker.py
apps/workers/tradingagents_bridge/worker.py
apps/workers/analytics_sink/worker.py
apps/workers/cold_storage/worker.py
```

## 2. 目錄結構

```text
stock-py/
├── apps/
│   ├── public_api/          # public FastAPI app
│   ├── admin_api/           # admin FastAPI app
│   ├── scheduler/           # scheduled jobs
│   └── workers/             # scanner / notification / analytics / market-data workers
├── domains/                 # domain services / policies / repositories
├── infra/                   # DB / events / security / analytics / storage / HTTP
├── alembic/                 # schema migrations
├── tests/                   # unit + contract + e2e + load + targeted integration tests
├── ops/                     # runbooks + load/cutover report templates
└── docs/                    # architecture + historical migration handbooks
```

## 3. 文件對應

### Public API
- apps/public_api/main.py → public FastAPI app 與 middleware 組裝
- apps/public_api/routers/auth.py → auth
- apps/public_api/routers/account.py → account / subscription entry
- apps/public_api/routers/watchlist.py → watchlist CRUD
- apps/public_api/routers/portfolio.py → portfolio CRUD
- apps/public_api/routers/search.py → symbol search
- apps/public_api/routers/notifications.py → notification center
- apps/public_api/routers/trades.py → trade info / confirm / ignore / adjust
- apps/public_api/routers/ui.py + frontend/app + frontend/platform + frontend/admin → FastAPI-served static HTML/JS surfaces for subscriber / platform / admin
- apps/public_api/routers/signal_ingest.py → internal signal ingest
- apps/public_api/routers/tradingagents_submit.py + tradingagents_webhook.py → TradingAgents internal submit / terminal webhook

### Admin API
- apps/admin_api/main.py → admin FastAPI app + require_admin
- apps/admin_api/routers/acceptance.py → QA / cutover acceptance readiness and latest report artifacts
- apps/admin_api/routers/analytics.py → high-privilege analytics dashboards for platform strategy review and admin governance
- apps/admin_api/routers/audit.py → audit event read model over durable outbox
- apps/admin_api/routers/backtests.py → high-privilege backtest run list / detail / trigger APIs; product-owned by the platform strategy surface
- apps/admin_api/routers/anomalies.py → OHLCV anomaly review surface
- apps/admin_api/routers/distribution.py → manual distribution message command surface
- apps/admin_api/routers/operators.py → durable operator list / role update APIs
- apps/admin_api/routers/runtime_monitoring.py → runtime heartbeat registry, component list/detail, and aggregated stats / health / metrics views
- apps/admin_api/routers/scanner.py → high-privilege scanner observability / live-decision views for platform strategy operations
- apps/admin_api/routers/signal_stats.py → high-privilege signal generation summary and list; product-owned by the platform strategy surface
- apps/admin_api/routers/tasks.py → receipts / emails / outbox / trades operational task center, including ack, claim, retry, stale-release, trade-claim, and trade-expire actions
- apps/admin_api/routers/tradingagents.py → TradingAgents internal admin views / reconcile for platform strategy operations
- apps/admin_api/routers/users.py → admin user operations list / detail / update / bulk update
- apps/admin_api/dependencies.py → admin read model service wiring

### Workers / Async Flows
- domains/signals/* + apps/workers/scanner/* → signal generation / scanner
- domains/market_data/* + apps/workers/market_data/* → market data import / quality / sync
- infra/db/models/events.py + infra/events/outbox.py + apps/workers/event_pipeline/* → durable event outbox relay + Redis Streams dispatch
- domains/notifications/* + apps/workers/notification_orchestrator + push_dispatch + email_dispatch + receipt_escalation → notification delivery chain
- domains/notifications/retention_service.py + apps/workers/retention/* → notification/event retention maintenance, including terminal receipt archive and terminal outbox cleanup
- domains/tradingagents/* + apps/workers/tradingagents_bridge/* → TradingAgents async integration
- domains/analytics/* + apps/workers/analytics_sink + cold_storage → analytics aggregation / archive
- apps/scheduler/main.py → periodic orchestration

### Infra
- infra/db/* → SQLAlchemy models / session / UoW
- infra/events/* → durable outbox helpers / Redis broker / subscriber bootstrap
- infra/security/* → auth, token, idempotency
- infra/http/* → health + HTTP client
- infra/analytics/* + infra/storage/* → monthly-partitioned local analytics facade / object storage abstraction
- infra/observability/* → metrics / tracing / runtime heartbeat registry

## 4. 當前實作說明

- `public_api` 同時承接原先 subscriber 與 platform 需要的後端能力，不再按舊 `app/platform/subscriber` 目錄拆分。
- `/app`、`/platform`、`/admin` 現在由 Python 直接輸出 HTML shell；若流量經過 nginx，三端頁面可以同 host 直連 public/admin API，否則可透過 query string 覆寫 base URL。
- `admin_api` 現在同時承載兩類能力：一類是管理端真正主責的 users / operators / distribution / tasks / audit / runtime / acceptance；另一類是暫時集中在高權限內部控制面下的 backtests / scanner / signal stats / analytics / TradingAgents。後者從產品歸屬上仍應視為 platform 核心的一部分。
- analytics 層目前可本地運行，但仍是文件型 facade，不是生產級 ClickHouse/Kafka 部署。
- 倉庫目前已具備獨立 backend / worker / ops 邊界，也已把三端 UI 收回到 Python 服務本身；目前剩餘前端工作重點是把 platform 和 admin 的信息架構拉回正確產品邊界，而不是再擴散職責。
- 倉庫目前已落地 `tests/unit/*`、`tests/contract/*`、`tests/e2e/*`、`tests/load/*`，以及 `tests/integration/account/*`、`tests/integration/admin/*`、`tests/integration/analytics/*`、`tests/integration/notifications/*`、`tests/integration/trades/*`、`tests/integration/tradingagents/*` 的 targeted integration coverage。
- `ops/runbooks/qa-cutover-checklist.md` 與 `ops/reports/load/*`、`ops/reports/cutover/*` 模板可直接用於 staging baseline 與 canary / rollback 留痕。

### 4.1 桌面端需求與現狀對齊

- 需求 1：候選標的與入場研究應集中在平台端。
	現狀：`/platform` 已承接 symbol search、觀察池操作與入場分數維護；對應 public API 為 `/v1/search/*` 與 `/v1/watchlist/*`。
- 需求 2：退出策略、持倉與交易執行應與策略判斷保持同屏閉環。
	現狀：平台端已具備 portfolio CRUD、退出參數維護與 trade lookup / confirm / ignore / adjust；對應 public API 為 `/v1/portfolio/*` 與 `/v1/trades/*`。
- 需求 3：回測、勝率、排名、scanner 決策觀測與策略健康度屬於平台核心，而非 admin 主產品面。
	現狀：`/platform` 已把這些能力統一表述為「內部策略接口台」，但底層仍主要經 `/v1/admin/backtests/*`、`/v1/admin/scanner/*`、`/v1/admin/signal-stats/*`、`/v1/admin/analytics/*`、`/v1/admin/tradingagents/*` 取數，屬於產品歸屬已對齊、技術掛載仍過渡中的狀態。
- 需求 3.1：桌面端上的高權限策略操作，必須能自行完成 session 化認證，而不是要求操作者切去 admin 再回來。
	現狀：`/platform` 已內嵌 `/v1/admin-auth/send-code`、`/v1/admin-auth/verify`、`/v1/admin-auth/refresh` 的入口，作為策略工作台自己的高權限登入流；`admin_api` 仍要求 access token 對應有效 `SessionModel`，所以只生成簽名 JWT 而不建立 session 時，請求會得到 `session_revoked`。
- 需求 4：桌面端應作為後續前端開發主戰場。
	現狀：`/platform` 已作為桌面端唯一工作台，後續桌面端增量開發應直接落在這個入口，而不是維持額外的並行版本路由。
- 結論：桌面端的產品邊界已經明確，現階段不需要再討論它是不是“研究/查詢頁”；真正的開發任務是把高權限策略能力逐步從 admin 敘事中抽離，持續向 platform 工作台收口。