# stock-py 當前後端架構

> 狀態（2026-04-04）：本文描述當前 Python 3.13 倉庫已落地的後端、worker 與目錄對應。容量藍圖與尚未完成的 target state 請看 `docs/python-migration/resume.md`。

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
- market-data anomalies 查詢
- analytics read model 查詢
- backtest runs / latest rankings 管理
- signal stats 查詢
- scanner observability / live-decision 查詢
- runtime monitoring、tasks center、operators 與 distribution manual command 操作
- TradingAgents admin 查詢與補償操作
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
└── docs/                    # architecture + migration handbooks
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
- apps/public_api/routers/signal_ingest.py → internal signal ingest
- apps/public_api/routers/tradingagents_submit.py + tradingagents_webhook.py → TradingAgents internal submit / terminal webhook

### Admin API
- apps/admin_api/main.py → admin FastAPI app + require_admin
- apps/admin_api/routers/acceptance.py → QA / cutover acceptance readiness and latest report artifacts
- apps/admin_api/routers/analytics.py → analytics dashboards
- apps/admin_api/routers/audit.py → audit event read model over durable outbox
- apps/admin_api/routers/backtests.py → backtest run list / detail / trigger APIs
- apps/admin_api/routers/anomalies.py → OHLCV anomaly review surface
- apps/admin_api/routers/distribution.py → manual distribution message command surface
- apps/admin_api/routers/operators.py → durable operator list / role update APIs
- apps/admin_api/routers/runtime_monitoring.py → runtime heartbeat registry, component list/detail, and aggregated stats / health / metrics views
- apps/admin_api/routers/scanner.py → scanner observability / live-decision views
- apps/admin_api/routers/signal_stats.py → signal generation summary and list
- apps/admin_api/routers/tasks.py → receipts / emails / outbox / trades operational task center, including ack, claim, retry, stale-release, trade-claim, and trade-expire actions
- apps/admin_api/routers/tradingagents.py → TradingAgents admin views / reconcile
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
- `admin_api` 目前除了 analytics 與 TradingAgents 視圖，已補上 anomalies、backtests、scanner、signal stats、operators、distribution manual-message、receipts / emails / outbox / trades claim/expire task console、runtime component list/detail 與 stats / health / metrics，以及 users / audit / acceptance 管理查詢面。
- analytics 層目前可本地運行，但仍是文件型 facade，不是生產級 ClickHouse/Kafka 部署。
- 倉庫目前已落地 `tests/unit/*`、`tests/contract/*`、`tests/e2e/*`、`tests/load/*`，以及 `tests/integration/account/*`、`tests/integration/admin/*`、`tests/integration/analytics/*`、`tests/integration/notifications/*`、`tests/integration/trades/*`、`tests/integration/tradingagents/*` 的 targeted integration coverage。
- `ops/runbooks/qa-cutover-checklist.md` 與 `ops/reports/load/*`、`ops/reports/cutover/*` 模板可直接用於 staging baseline 與 canary / rollback 留痕。