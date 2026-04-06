# Stock 全量 Python 化與 300 萬 DAU 改造藍圖

版本：v1.1（QA 強化版）  
日期：2026-04-04  
適用對象：架構組、後端組、資料組、平台組、測試組、運維組、產品技術負責人

> 狀態（2026-04-04）：本文同時承擔「當前 Python 3.13 repo 現況」與「300 萬 DAU target-state 藍圖」。第 2 章描述已落地基線；後續章節若列出 repo 中尚不存在的 `tests/integration`、`tests/contract`、`tests/e2e`、`tests/load`、K8s 或 runbook 目錄，表示待補交付，不代表現況已全部完成。

---

## 1. 文檔定位

本文不是概念提案，而是可直接交給多個團隊並行開發的實施基線。

本文回答五個問題：

1. 現有 `stock` 專案有哪些真實功能與運行單元。
2. 如何將現有 Node.js/TypeScript 後端、worker、scanner、管理 API、資料處理鏈路全面改造為 Python。
3. 如何把架構從目前單機 / 小集群模式提升到支撐 300 萬 DAU 的等級。
4. 每個功能點應由哪個 Python 模塊或服務承接，資料如何存，事件如何流，驗收標準是什麼。
5. 其他團隊拿到本文後，應以什麼順序、什麼倉庫結構、什麼交付物直接開始開發。

### 1.1 本文對「整個項目改造為 Python」的定義

瀏覽器端的 `/app`、`/platform`、`/admin` 仍保留 React/TypeScript，因為前端在瀏覽器中執行，無法合理地用 Python 取代。

本方案中的「整個項目改造為 Python」定義為：

- 所有服務端 API 改為 Python。
- 所有 background worker 改為 Python。
- 所有 scanner / backtest / retention / notification / reconciliation 鏈路改為 Python。
- 所有 admin API、運維 API、內部 webhook 接收器改為 Python。
- 所有部署入口、環境配置、資料遷移、任務調度、腳本與測試基建統一為 Python。
- 前端保留現有 React，但所有 API contract 改由 Python FastAPI 產出的 OpenAPI 驅動。

### 1.2 本文的交付目標

完成本文件後，團隊應能直接啟動以下工作：

- 建立 Python 單體倉庫或 monorepo。
- 建立基礎資料層與遷移框架。
- 逐域搬遷現有功能。
- 建立 300 萬 DAU 的容量與部署基線。
- 在不破壞現有業務口徑的前提下完成切流。

### 1.3 團隊拆分文檔

為了讓不同團隊可以直接拿走自己的施工手冊，本文件已拆分出一套團隊文檔包，位於：

- `docs/python-migration/README.md`
- `docs/python-migration/PLATFORM_TEAM_EXECUTION.md`
- `docs/python-migration/ACCOUNT_TEAM_EXECUTION.md`
- `docs/python-migration/SIGNAL_TEAM_EXECUTION.md`
- `docs/python-migration/NOTIFICATION_TEAM_EXECUTION.md`
- `docs/python-migration/AI_INTEGRATION_TEAM_EXECUTION.md`
- `docs/python-migration/DATA_TEAM_EXECUTION.md`
- `docs/python-migration/QA_TEAM_EXECUTION.md`

使用方式：

1. 技術負責人先讀本文件。
2. 各團隊再只讀自己的執行手冊。
3. 任務系統拆分時，以團隊手冊為直接輸入。

---

## 2. 現況基線

### 2.1 當前服務面

當前倉庫已完成 Python 3.13 後端骨架，主要由三類運行單元組成：

- `apps/public_api`：承接 auth、account、watchlist、portfolio、search、notifications、trades，以及 internal signal / TradingAgents hooks。
- `apps/admin_api`：承接 anomalies、analytics、backtests、distribution、operators、runtime、scanner、signal stats、tasks、TradingAgents，以及 users / audit / acceptance 管理查詢面，其中 tasks center 已覆蓋 receipts、emails、outbox 與 trades claim / expire 的主要運營動作，runtime 面已覆蓋 component list/detail 與 stats / health / metrics 聚合視圖。
- `apps/scheduler` 與 `apps/workers/*`：承接 scanner、market data、notification、TradingAgents、analytics、cold storage 等背景流程。

### 2.2 當前後端 API 面

目前 Python FastAPI 倉庫已落地的路由群組如下：

| 路由群組 | 主要職責 | 現有能力 |
|---|---|---|
| `/v1/auth` | 驗證碼登入 | 發碼、驗碼、登出、refresh |
| `/v1/account` | 帳戶與訂閱狀態 | dashboard、profile、開始訂閱 |
| `/v1/watchlist` | 關注清單 | CRUD |
| `/v1/portfolio` | 持倉 | CRUD、停利停損參數 |
| `/v1/search` | 股票搜尋 | symbol/name fuzzy search |
| `/v1/notifications` | 通知中心 | 通知列表、已讀、ack、push 裝置管理、測試推送 |
| `/v1/trades` | 交易建議與確認 | 外鏈確認、App 內確認、忽略、調整 |
| `/v1/internal/signals` | 內部訊號接入 | 桌面端 / scanner signal ingest |
| `/v1/internal/tradingagents` | TradingAgents internal hooks | submit / terminal webhook |
| `/v1/admin/*` | 管理後台統計與運營面 | acceptance、anomalies、analytics、audit、backtests、distribution、operators、runtime、scanner、signal stats、tasks、TradingAgents、users |
| `/health`、`/metrics` | 健康檢查與觀測 | readiness/liveness、metrics snapshot |

### 2.3 當前 background processes

目前倉庫中的 Python 背景入口如下：

- `apps/scheduler/main.py`
- `apps/workers/scanner/worker.py`
- `apps/workers/market_data/worker.py`
- `apps/workers/backtest/worker.py`
- `apps/workers/notification_orchestrator/worker.py`
- `apps/workers/push_dispatch/worker.py`
- `apps/workers/email_dispatch/worker.py`
- `apps/workers/receipt_escalation/worker.py`
- `apps/workers/retention/worker.py`
- `apps/workers/tradingagents_bridge/worker.py`
- `apps/workers/analytics_sink/worker.py`
- `apps/workers/cold_storage/worker.py`

### 2.4 當前資料資產

目前核心資料主要分成兩層：

- PostgreSQL OLTP：使用者與登入、帳戶與訂閱、watchlist / portfolio、signals / scanner、notifications / receipts、trade workflow、TradingAgents 分析記錄。
- 本地 analytics facade：`infra/analytics/clickhouse_client.py` 以 JSONL 形式落地 analytics event，`infra/storage/object_storage.py` 以本地路徑模擬 object storage，用於 archive 與本地開發。

### 2.5 當前已知優勢

- 對外 API 與主要 worker 已遷移到 Python 3.13 倉庫。
- `apps / domains / infra` 結構已成型，責任邊界清晰。
- outbox、event bus、subscriber bootstrap、observability 基礎件已落地。
- analytics read model 已從 admin router 中抽離到獨立 repository / service 結構。
- TradingAgents 仍維持非阻塞異步整合模式。

### 2.6 當前已知瓶頸

- scanner 與通知 worker 仍是單入口實作，尚未完成真正水平擴展驗證。
- analytics 層目前仍是本地文件型 facade，尚未接入真 ClickHouse / Kafka / S3。
- `tests/contract`、`tests/e2e`、`tests/load`、runbook 已落地；`tests/integration` 仍在逐域補齊，目前已有 account、analytics、notifications、trades 與 TradingAgents integration baseline。
- 一部分部署與運維文檔仍保留 target-state 描述，尚未全部轉成 as-built 文檔。

---

## 3. 300 萬 DAU 目標與容量假設

### 3.1 目標 SLA / SLO

- `/api/auth/*`：P95 < 300ms，P99 < 800ms
- `/api/account`、`/api/watchlist`、`/api/portfolio`：P95 < 250ms
- `/api/search`：P95 < 120ms
- `/api/notifications`：P95 < 300ms
- `/admin-api` 常用查詢：P95 < 800ms
- 通知寫入到 outbox：P95 < 150ms
- Push dispatch 進入 provider：95% 在 30 秒內開始投遞
- TradingAgents submit：P95 < 300ms
- TradingAgents terminal result 落庫：99% 在 terminal 後 60 秒內完成

### 3.2 容量規劃假設

以下是假設值，團隊可在灰度期按真實指標微調，但所有設計與壓測必須至少覆蓋此級別：

| 指標 | 規劃值 |
|---|---|
| DAU | 3,000,000 |
| 峰值同時在線使用者 | 180,000 到 240,000 |
| 每日登入 / 驗證碼請求 | 1,200,000 |
| 每日帳戶首頁讀取 | 18,000,000 |
| 每日 watchlist / portfolio 讀取 | 30,000,000 |
| 每日訂閱關鍵同步寫入 | 3,000,000 |
| 每日通知列表讀取 | 36,000,000 |
| 每日通知已讀 / ack 寫入 | 12,000,000 |
| 每日交易確認 / 忽略 / 調整 | 1,500,000 |
| 每日唯一活躍標的 | 8,000 到 20,000 |
| 每 5 分鐘需評估的活躍標的集合 | 5,000 到 15,000 |
| 每日 AI 深度分析請求 | 100,000 到 300,000 |
| 通知爆發峰值 | 300,000 到 1,000,000 條 / 5 分鐘 |

### 3.3 容量設計結論

從上述假設反推，本專案不能再以單一 API + 單一 scanner + 單一分發 worker 的模式運行，必須滿足：

- 公網 API 可水平擴展。
- scanner 可分片並行。
- 分發與回執鏈路必須事件驅動。
- 讀寫模型必須分離。
- 熱資料與分析資料必須分庫或分用途存放。

---

## 4. 改造總原則

1. 不改變現有業務口徑，除非明確標記為 bug fix 或容量治理。
2. 不把 TradingAgents 變成同步阻塞依賴。
3. 不把 300 萬 DAU 問題只理解成 API QPS 問題，真正熱點在通知、scanner、資料分層、admin 查詢與長尾補償。
4. 不在第一階段把系統打碎成過度微服務；先建立 Python 模塊化單體 + 可獨立部署進程，再逐步拆分高壓域。
5. 所有寫操作都必須具備冪等設計。
6. 所有關鍵非同步鏈路都必須具備 outbox、retry、dead-letter、人工補償能力。
7. 所有 API contract 以 OpenAPI 為唯一來源，前端不得手寫隱式契約。
8. 所有資料庫 schema 變更只允許透過 Alembic 管理。
9. 所有事件 topic / queue 必須有明確 owner、payload schema 與重試策略。
10. 所有上線都要支援灰度、雙寫、回滾與審計。

---

## 5. 目標技術選型

本節給出唯一建議，不保留多選項，避免團隊在啟動期反覆爭論。

### 5.1 後端與服務框架

- Python：3.13
- API 框架：FastAPI
- ASGI Server：Uvicorn + Gunicorn
- Schema / 驗證：Pydantic v2
- ORM / SQL：SQLAlchemy 2.0 async + `asyncpg`
- Migration：Alembic
- HTTP client：`httpx`
- Cache / session / rate limit：Redis 7 Cluster
- 事件總線：Kafka 或 Redpanda
- 任務調度：APScheduler + Kafka consumer workers
- 指標：Prometheus + OpenTelemetry
- 日誌：JSON structured logging
- 追蹤：OpenTelemetry + Tempo 或 Jaeger
- 冷存：S3 或 MinIO
- 分析庫：ClickHouse

### 5.2 為何採 Kafka / Redpanda

對 300 萬 DAU，以下鏈路不適合只靠資料庫輪詢：

- 通知投遞
- 回執狀態變化
- scanner 產生的 signal fanout
- watchlist / portfolio 變更導致的 active symbol refresh
- TradingAgents terminal event
- admin 審計事件

Kafka / Redpanda 用於：

- 高吞吐事件分發
- 重播與補償
- 消費者群組水平擴展
- 與 ClickHouse / S3 做資料下沉

### 5.3 為何引入 ClickHouse

以下查詢不應與主業務 OLTP 庫搶資源：

- admin 大盤統計
- 策略績效排名
- signal_stats / outcomes 長時間窗分析
- 消息投遞與回執運營統計
- TradingAgents 分析審計視圖
- 壓測與容量觀測看板

### 5.4 為何前端保留 React

- 現有三端前端已形成清晰路由面與頁面資產。
- 直接重寫前端無法提升 300 萬 DAU 容量，反而會拖慢後端遷移。
- 正確做法是讓前端繼續使用 React，但把 API client 與 typed contract 改為從 Python OpenAPI 自動生成。

---

## 6. 目標系統拓撲

### 6.1 邏輯拓撲

```text
Browser (/app, /platform, /admin)
        |
        v
CDN / Nginx / WAF
        |
        +-----------------------> public-api (FastAPI)
        |
        +-----------------------> admin-api (FastAPI)
                                   |
                                   v
                           Python domain modules
                                   |
         +-------------------------+--------------------------+
         |                         |                          |
         v                         v                          v
   PostgreSQL/Citus           Redis Cluster            Kafka/Redpanda
         |                         |                          |
         |                         |                          +--> scanner workers
         |                         |                          +--> notification workers
         |                         |                          +--> receipt escalation workers
         |                         |                          +--> tradingagents bridge workers
         |                         |                          +--> retention / backfill workers
         |
         +-----------------------> ClickHouse
         +-----------------------> S3 / MinIO (archive, reports, cold payload)
```

### 6.2 最終 deployable units

| Deploy Unit | 角色 | 是否對外 |
|---|---|---|
| `public-api` | `/api/*` 與內部非 admin 公共入口 | 是 |
| `admin-api` | `/admin-api/*` 與運營控制面 | 否，僅內網 / VPN |
| `scheduler` | 定時任務調度入口 | 否 |
| `scanner-worker` | 訊號掃描與策略執行 | 否 |
| `notification-orchestrator` | signal -> notification outbox | 否 |
| `push-dispatch-worker` | Web Push / FCM / APNS 投遞 | 否 |
| `email-dispatch-worker` | SES / Resend 郵件投遞 | 否 |
| `receipt-escalation-worker` | ack timeout / 人工跟進升級 | 否 |
| `tradingagents-bridge-worker` | submit / poll / webhook reconciliation | 否 |
| `backtest-worker` | ranking / evidence / degradation refresh | 否 |
| `retention-worker` | 分區維護、歸檔、清理 | 否 |
| `market-data-worker` | symbol metadata、OHLCV、品質檢查 | 否 |

### 6.3 Python monorepo 結構

```text
stock-python/
├── pyproject.toml
├── README.md
├── apps/
│   ├── public_api/
│   │   ├── main.py
│   │   ├── dependencies.py
│   │   └── routers/
│   ├── admin_api/
│   │   ├── main.py
│   │   └── routers/
│   ├── scheduler/
│   │   └── main.py
│   └── workers/
│       ├── scanner/
│       ├── notification_orchestrator/
│       ├── push_dispatch/
│       ├── email_dispatch/
│       ├── receipt_escalation/
│       ├── tradingagents_bridge/
│       ├── backtest/
│       ├── retention/
│       └── market_data/
├── domains/
│   ├── auth/
│   ├── account/
│   ├── subscription/
│   ├── watchlist/
│   ├── portfolio/
│   ├── search/
│   ├── signals/
│   ├── notifications/
│   ├── trades/
│   ├── admin/
│   ├── tradingagents/
│   ├── market_data/
│   ├── analytics/
│   └── system/
├── infra/
│   ├── db/
│   ├── cache/
│   ├── events/
│   ├── observability/
│   ├── security/
│   └── storage/
├── alembic/
├── contracts/
│   ├── openapi/
│   └── events/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── e2e/
│   └── load/
└── ops/
    ├── docker/
    ├── k8s/
    ├── prometheus/
    └── runbooks/
```

---

## 7. 事件與資料流設計

### 7.1 事件 topic 清單

| Topic | Producer | Consumer | 用途 |
|---|---|---|---|
| `account.subscription.started` | public-api | scanner-worker、analytics | 開始訂閱快照生效 |
| `watchlist.changed` | public-api | active-symbol-refresher、analytics | 關注清單變更 |
| `portfolio.changed` | public-api | active-symbol-refresher、analytics | 持倉變更 |
| `signal.generated` | scanner-worker | notification-orchestrator、analytics | 產生 signal |
| `notification.requested` | notification-orchestrator | push/email workers | 進入分發 |
| `notification.delivered` | push/email workers | receipts、analytics | provider 投遞結果 |
| `notification.acknowledged` | public-api | receipt-escalation、analytics | 使用者 ack |
| `trade.action.recorded` | public-api | portfolio projection、analytics | 確認 / 忽略 / 調整 |
| `tradingagents.requested` | scanner/admin | tradingagents-bridge-worker | 提交 AI 深度分析 |
| `tradingagents.terminal` | webhook / poller | admin、analytics、notification | AI 終態 |
| `marketdata.symbol.updated` | market-data-worker | search、scanner | symbol metadata 更新 |
| `marketdata.ohlcv.imported` | market-data-worker | scanner、backtest | OHLCV 到位 |
| `ops.audit.logged` | all services | ClickHouse / archive | 審計與運營軌跡 |

### 7.2 Outbox 原則

所有跨服務或跨 worker 的非同步操作，一律使用 outbox pattern：

- 主交易在 PostgreSQL 中提交成功。
- 同交易內寫入 `outbox_events`。
- outbox relay 將事件投遞到 Kafka。
- consumer 端以 `event_id` 冪等消費。

這條規則適用於：

- 開始訂閱
- watchlist / portfolio 更新
- signal 寫入與 fanout
- notification requested
- receipt state change
- trade state change
- TradingAgents terminal result

---

## 8. 功能域詳細改造

本章是本文核心。每個功能點都要回答：誰負責、資料怎麼存、對外接口是什麼、非同步怎麼走、如何驗收。

### 8.1 認證與會話

#### 8.1.1 現有功能點

- 郵箱驗證碼發送。
- 驗證碼驗證。
- 登出撤銷 session。
- 開發環境允許回傳 `devCode`。
- IP / email 維度限流。

#### 8.1.2 Python 目標模塊

- `domains/auth/service.py`
- `domains/auth/repository.py`
- `apps/public_api/routers/auth.py`
- `infra/security/jwt.py`
- `infra/cache/rate_limit.py`

#### 8.1.3 目標接口

- `POST /v1/auth/send-code`
- `POST /v1/auth/verify`
- `POST /v1/auth/logout`
- `POST /v1/auth/refresh`，新系統新增，替代前端長期持有單一 session token 的風險

#### 8.1.4 資料模型

- 保留 `users`
- 保留 `email_codes`
- 保留 `sessions`
- 新增 `login_attempts` 或 Redis 限流 key，不落 PostgreSQL 也可

#### 8.1.5 Redis 設計

- `auth:send-code:ip:{ip}`
- `auth:send-code:email:{email}`
- `auth:verify:ip:{ip}`
- `session:token:{token_hash}`

#### 8.1.6 開發要求

- 驗證碼只允許單次使用。
- 所有 session token 只存 hash，不存明文。
- 新增 refresh token 輪換能力。
- `devCode` 僅允許 `ENV != prod` 且 host 為 localhost 時出現。
- 所有 auth 返回的錯誤文案與當前產品口徑對齊。

#### 8.1.7 驗收標準

- 同 email 60 秒內不可重複發碼。
- 驗碼後自動 upsert user，與現有行為保持一致。
- 登出後舊 token 立即失效。
- 壓測下 2000 RPS auth burst 不打穿資料庫。

#### 8.1.8 工單拆分

- `AUTH-01`：Pydantic schema 與 OpenAPI
- `AUTH-02`：驗證碼 repository 與 session repository
- `AUTH-03`：郵件 provider adapter
- `AUTH-04`：Redis rate limiter
- `AUTH-05`：refresh token 機制
- `AUTH-06`：本地 devCode gate
- `AUTH-07`：單元 / 合約 / 壓測案例

### 8.2 帳戶、資產與開始訂閱

#### 8.2.1 現有功能點

- 讀取個人資料、總資金、可用現金、watchlist 統計、portfolio 統計、push device 數。
- 更新名稱、語言、時區、總資金、幣別。
- `POST /api/account/start-subscription` 可一次同步 account、watchlist、portfolio，並將 `users.extra.subscription` 置為 active，保存 snapshot。

#### 8.2.2 Python 目標模塊

- `domains/account/`
- `domains/subscription/`
- `apps/public_api/routers/account.py`

#### 8.2.3 目標接口

- `GET /v1/account/profile`
- `GET /v1/account/dashboard`
- `PUT /v1/account/profile`
- `POST /v1/account/start-subscription`

#### 8.2.4 資料模型

- 保留 `user_account`
- 保留 `users.extra.subscription`
- 新增 `subscription_snapshots`，將關鍵同步快照從 `users.extra` 部分拆出，便於審計與回滾

#### 8.2.5 改造要求

- `users.extra.subscription` 在 Phase 1 保留，用於兼容現有前端。
- 新系統寫入時同步寫 `subscription_snapshots`。
- `start-subscription` 需要支援冪等鍵 `X-Idempotency-Key`。
- 觸發成功後發出 `account.subscription.started` 事件。
- 對 plan limit 驗證保持與現有 `watchlist` / `portfolio` 限制一致。

#### 8.2.6 驗收標準

- `draft -> active` 與現有規則一致。
- 沒有總資金、沒有 watchlist、空倉且未允許 empty portfolio 時，返回與當前一致的阻擋錯誤。
- 兩次重放同一 `X-Idempotency-Key` 只生效一次。

#### 8.2.7 工單拆分

- `SUB-01`：account read model
- `SUB-02`：start-subscription command handler
- `SUB-03`：subscription snapshot table + migration
- `SUB-04`：plan limit policy service
- `SUB-05`：idempotency middleware
- `SUB-06`：事件投遞與 replay 測試

### 8.3 Watchlist

#### 8.3.1 現有功能點

- watchlist CRUD
- `notify` 開關
- `min_score` 閾值
- symbol 去重與規範化
- 開始訂閱前與開始訂閱後都可維護

#### 8.3.2 Python 目標模塊

- `domains/watchlist/`
- `apps/public_api/routers/watchlist.py`

#### 8.3.3 目標接口

- `GET /v1/watchlist`
- `POST /v1/watchlist`
- `PUT /v1/watchlist/{id}`
- `DELETE /v1/watchlist/{id}`

#### 8.3.4 資料與事件

- 保留 `user_watchlist`
- 每次變更寫 outbox
- 發送 `watchlist.changed`
- 維護 `active_symbols_materialization` 投影表或 Redis set

#### 8.3.5 改造要求

- 所有 symbol 在 domain 層統一 `trim + upper`。
- 依 `user_id` 查詢走主分片鍵。
- 更新成功後不直接觸發重掃全量，只標記 symbol dirty。

#### 8.3.6 驗收標準

- 單使用者 1000 筆 watchlist 讀取仍在 P95 < 200ms。
- 同 symbol 重複新增返回明確錯誤。
- watchlist 變更會在 30 秒內反映到 active symbols materialization。

#### 8.3.7 工單拆分

- `WL-01`：CRUD router
- `WL-02`：symbol normalization policy
- `WL-03`：dirty-flag / projection update
- `WL-04`：事件冪等消費
- `WL-05`：容量壓測

### 8.4 Portfolio

#### 8.4.1 現有功能點

- 持倉 CRUD
- 平均成本、停利、停損、通知開關、備註
- 交易確認後自動反寫持倉
- buy/add 後重置 sell progress

#### 8.4.2 Python 目標模塊

- `domains/portfolio/`
- `domains/trades/portfolio_projection.py`
- `apps/public_api/routers/portfolio.py`

#### 8.4.3 目標接口

- `GET /v1/portfolio`
- `POST /v1/portfolio`
- `PUT /v1/portfolio/{id}`
- `DELETE /v1/portfolio/{id}`

#### 8.4.4 資料與事件

- 保留 `user_portfolio`
- 交易確認後發送 `trade.action.recorded`
- portfolio projector 異步更新持倉衍生視圖

#### 8.4.5 改造要求

- 在資料層明確區分 command model 與 dashboard read model。
- portfolio 更新與 trade apply 必須走單一 domain service，不能在多個 router 各自改表。
- 對空格 symbol、plan limit、重複 symbol 保持與現有修正後行為一致。

#### 8.4.6 驗收標準

- 交易確認後，持倉變化與通知 ack 在同一業務流程內可追溯。
- portfolio dashboard 在高併發讀下不產生鎖等待熱點。

#### 8.4.7 工單拆分

- `PF-01`：portfolio command/query separation
- `PF-02`：trade -> portfolio projector
- `PF-03`：extra JSON 字段正規化
- `PF-04`：plan limit guard
- `PF-05`：資產快照 read model

### 8.5 Symbol Search 與市場標的資料

#### 8.5.1 現有功能點

- `symbols` 表支援名稱與代碼 fuzzy search
- 透過 GIN trigram 索引加速

#### 8.5.2 Python 目標模塊

- `domains/search/`
- `domains/market_data/symbols/`
- `apps/public_api/routers/search.py`

#### 8.5.3 目標接口

- `GET /v1/search/symbols?q=`
- `POST /internal/market-data/symbols/rebuild-index`

#### 8.5.4 改造要求

- 早期繼續使用 PostgreSQL trigram。
- 只有當 symbol universe 超過目前數量級且搜尋與主庫競爭明顯時，才評估 OpenSearch。
- symbol metadata 同步由 `market-data-worker` 負責。

#### 8.5.5 驗收標準

- 10k 到 100k symbols 規模下搜尋 P95 < 120ms。
- 不允許 search service 直接依賴前端拼接 SQL。

#### 8.5.6 工單拆分

- `SEARCH-01`：query builder
- `SEARCH-02`：symbol metadata sync pipeline
- `SEARCH-03`：cache with stale-while-revalidate

### 8.6 Signal Ingest、Scanner 與策略治理

#### 8.6.1 現有功能點

- 桌面端可透過 `/api/signals/desktop` 上報訊號。
- scanner 定期讀 active symbols，生成 buy / sell / add / stop_loss 類信號。
- 使用 ranking、regime、historical signal stats、degradation penalty 做策略選擇。
- backtest refresh scheduler 可刷新策略排名與證據。

#### 8.6.2 Python 目標模塊

- `domains/signals/`
- `domains/analytics/backtest/`
- `apps/workers/scanner/`
- `apps/workers/backtest/`
- `apps/public_api/routers/signal_ingest.py`

#### 8.6.3 目標接口

- `POST /v1/internal/signals/desktop`
- `GET /v1/internal/scanner/runs/{run_id}`
- `POST /v1/internal/scanner/rebuild-active-symbols`
- `POST /v1/internal/backtest/refresh`

#### 8.6.4 目標設計

- `active_symbols` 不再臨時計算，而是維護為顯式投影表或 Redis sorted set。
- scanner 不再單實例輪詢全量，而是按 symbol bucket 分片。
- 每輪 scan 生成 `scanner_run`、`scanner_decision`、`signal_candidates` 審計資料。
- signal -> notification 改為事件驅動，不直接在 scanner 內 fanout 寫入多表。

#### 8.6.5 3M DAU 必須新增的能力

- 全局 signal dedupe：同一 symbol、同一策略窗、同一 regime 下避免短時間內重覆 fanout。
- 每個 symbol 的冷卻窗口與再觸發策略。
- 每個使用者的最低分門檻在 fanout 階段應用，而不是 scanner 重複計算。
- OHLCV 品質告警獨立化，從 `ohlcv_anomalies` 擴展到 symbol 資料健康模型。

#### 8.6.6 資料模型

- 保留 `signals`
- 新增 `scanner_runs`
- 新增 `scanner_decisions`
- 新增 `strategy_rankings_history`
- 新增 `symbol_signal_cooldowns`
- 新增 `signal_evidence_snapshots`

#### 8.6.7 驗收標準

- 15,000 活躍 symbols 在 5 分鐘週期內可完成掃描。
- scanner 任一 pod 故障時可由其他分片接管。
- 相同 signal 不會在冷卻窗口內重覆大規模通知。

#### 8.6.8 工單拆分

- `SIG-01`：active symbols projector
- `SIG-02`：scanner shard coordinator
- `SIG-03`：signal dedupe policy
- `SIG-04`：decision audit schema
- `SIG-05`：ranking refresh worker
- `SIG-06`：OHLCV quality pipeline
- `SIG-07`：load test for 15k symbols / 5min

### 8.7 Notifications、Push、Email 與回執

#### 8.7.1 現有功能點

- 通知列表查詢
- push 裝置綁定、停用、測試推送
- 單條已讀 / 全部已讀
- 單條 ack
- `message_outbox` 統一分發
- `message_receipts` 與 archive
- 人工跟進與升級 worker

#### 8.7.2 Python 目標模塊

- `domains/notifications/`
- `apps/workers/notification_orchestrator/`
- `apps/workers/push_dispatch/`
- `apps/workers/email_dispatch/`
- `apps/workers/receipt_escalation/`
- `apps/public_api/routers/notifications.py`

#### 8.7.3 目標接口

- `GET /v1/notifications`
- `PUT /v1/notifications/read-all`
- `PUT /v1/notifications/{id}/read`
- `PUT /v1/notifications/{id}/ack`
- `GET /v1/notifications/push-devices`
- `POST /v1/notifications/push-devices`
- `DELETE /v1/notifications/push-devices/{device_id}`
- `POST /v1/notifications/push-devices/{device_id}/test`

#### 8.7.4 目標鏈路

```text
signal.generated
  -> notification-orchestrator
  -> write notifications + outbox
  -> publish notification.requested
  -> push-dispatch-worker / email-dispatch-worker
  -> write message_receipts + delivery attempts
  -> publish notification.delivered
  -> receipt-escalation-worker watches overdue ack_required receipts
```

#### 8.7.5 重要改造點

- `notifications` 作為事實源保留。
- `message_outbox` 改為 append-only event envelope，避免反覆更新單行熱點。
- `message_receipts` 保留熱資料，`message_receipts_archive` 只保留已終態且超過 TTL 的資料。
- ack 與 opened 更新不得掃全表，必須按 `notification_id + user_id` 精確命中。
- `push_subscriptions` 應支援多 provider，但 Phase 1 先保留 `webpush` 主路。

#### 8.7.6 3M DAU 必須新增的能力

- provider 分流與失敗回退策略明確化。
- per-user / per-channel 通知頻控。
- 批量 fanout 時按 user shard / channel shard 拆分。
- dead-letter queue 與管理端 retry 工具。

#### 8.7.7 驗收標準

- 峰值 1,000,000 條 / 5 分鐘 notification.requested 可平穩進隊。
- 95% push/email 投遞任務在 30 秒內被 worker claim。
- ack API 在 5000 RPS 下不出現全表掃描。

#### 8.7.8 工單拆分

- `NOTIF-01`：notification command/query API
- `NOTIF-02`：outbox relay
- `NOTIF-03`：push dispatcher adapter
- `NOTIF-04`：email dispatcher adapter
- `NOTIF-05`：delivery attempts schema
- `NOTIF-06`：receipt escalation policy
- `NOTIF-07`：archive compactor
- `NOTIF-08`：DLQ + admin retry API

### 8.8 Trade Workflow

#### 8.8.1 現有功能點

- `/:id/info` 外鏈查看建議
- `/:id/confirm` 外鏈接受 / 忽略
- `/:id/app-info` App 內查看
- `/:id/app-confirm` App 內確認
- `/:id/app-ignore` App 內忽略
- `/:id/adjust` / `/:id/app-adjust` 記錄實際成交
- 外鏈 token 驗證與過期控制
- 確認後更新 portfolio 與回執

#### 8.8.2 Python 目標模塊

- `domains/trades/`
- `apps/public_api/routers/trades.py`
- `domains/trades/link_security.py`

#### 8.8.3 目標接口

- `GET /v1/trades/{id}/info`
- `GET /v1/trades/{id}/app-info`
- `POST /v1/trades/{id}/confirm`
- `POST /v1/trades/{id}/ignore`
- `POST /v1/trades/{id}/adjust`
- `POST /v1/trades/{id}/app-confirm`
- `POST /v1/trades/{id}/app-ignore`
- `POST /v1/trades/{id}/app-adjust`

#### 8.8.4 改造要求

- `trade_log` 保留為主表。
- link token 改為 HMAC + 過期時間 + 一次性 nonce。
- 對外鏈頁面可維持 HTML 回傳，也可由前端頁面接管，但後端必須保證同等安全性。
- 確認 / 忽略 / 調整之後，同步產生 `trade.action.recorded` 事件。

#### 8.8.5 驗收標準

- 同一交易無法重覆確認。
- 過期鏈接無法繞過檢查。
- 成交回寫 portfolio 與 ack receipt 的業務結果可追蹤。

#### 8.8.6 工單拆分

- `TRADE-01`：trade command service
- `TRADE-02`：signed-link verification
- `TRADE-03`：HTML confirm page or frontend handoff
- `TRADE-04`：trade -> portfolio projector
- `TRADE-05`：trade analytics sink

### 8.9 Admin 與運營控制台

#### 8.9.1 現有功能點

依據當前代碼與既有文檔，admin 至少覆蓋以下面向：

- 管理概覽
- 使用者查詢與管理
- signal stats / OHLCV anomalies 視圖
- tasks / outbox / receipts / distribution 視圖
- runtime monitoring
- scanner observability / live-decision
- backtest refresh / strategy health / backtest runs
- TradingAgents analyses 視圖
- 任務 claim / retry / expire / resolve 類操作
- audit 與系統配置

#### 8.9.2 Python 目標模塊

- `domains/admin/`
- `apps/admin_api/routers/overview.py`
- `apps/admin_api/routers/users.py`
- `apps/admin_api/routers/tasks.py`
- `apps/admin_api/routers/distribution.py`
- `apps/admin_api/routers/analytics.py`
- `apps/admin_api/routers/runtime_monitoring.py`
- `apps/admin_api/routers/tradingagents.py`
- `apps/admin_api/routers/system.py`

#### 8.9.3 資料層原則

- admin 重查詢優先讀 ClickHouse / 物化 read model。
- 不允許 admin 頁面直接拿大量 COUNT、CTE 長查詢壓主庫。
- 管理動作走 command API，審計事件寫 `ops.audit.logged`。

#### 8.9.4 新增要求

- operator / role / scope 模型正規化，淘汰 email whitelist。
- 所有 destructive action 必須二次確認與審計。
- 所有 bulk action 必須可回溯、可部分失敗、可重試。

#### 8.9.5 驗收標準

- admin 高峰查詢不影響 public API P95。
- 操作員權限可精確到 view / action scope。
- 任務類重試和 claim 行為有完整審計。

#### 8.9.6 工單拆分

- `ADMIN-01`：RBAC / scope model
- `ADMIN-02`：overview read model
- `ADMIN-03`：distribution read model
- `ADMIN-04`：tasks command endpoints
- `ADMIN-05`：TradingAgents admin view
- `ADMIN-06`：audit event ingestion
- `ADMIN-07`：system config service

### 8.10 Monitoring 與 Health

#### 8.10.1 現有功能點

- `/health`
- `/health/ready`
- `/health/live`
- `/metrics`
- `/admin-api/metrics`

#### 8.10.2 Python 當前模塊

- `infra/http/health.py`
- `infra/observability/metrics.py`
- `apps/public_api/main.py`
- `apps/admin_api/main.py`
- `apps/scheduler/main.py`

#### 8.10.3 新要求

- 每個 worker 需上報 heartbeat、lag、claim latency、queue depth。
- scanner 需上報每輪耗時、symbol 覆蓋數、成功率、抑制原因。
- notification worker 需上報 channel 成功率與 provider error rate。
- TradingAgents bridge 需上報 submit success、poll lag、webhook lag。

#### 8.10.4 驗收標準

- Prometheus 指標可直接驅動 Grafana 看板與告警。
- 任意 worker 停止 60 秒內觸發告警。

#### 8.10.5 工單拆分

- `OBS-01`：metrics SDK
- `OBS-02`：JSON logging baseline
- `OBS-03`：worker heartbeat registry
- `OBS-04`：runtime admin pages

### 8.11 TradingAgents 深度分析整合

#### 8.11.1 現有功能點

- stock 端已具備 submit、repository、polling、webhook receiver。
- `tradingagents_analysis_records` 已作為關聯與終態落庫表。
- webhook 與 polling 共同調和。
- 本地已驗證 mock mode 可走到 `succeeded`。

#### 8.11.2 Python 目標模塊

- `domains/tradingagents/`
- `apps/workers/tradingagents_bridge/`
- `apps/public_api/routers/tradingagents_webhook.py`
- `apps/admin_api/routers/tradingagents.py`

#### 8.11.3 目標設計

- stock Python 主系統不內嵌 TradingAgents graph；保持外部 Python 服務依賴。
- 本系統只保留 adapter / orchestration / persistence / reconciliation。
- request_id 仍由 stock 生成並作為業務主鍵。

#### 8.11.4 核心表

- 保留 `tradingagents_analysis_records`
- 新增 `tradingagents_submit_failures`，記錄 pre-accept submit fail
- 新增 `tradingagents_events`，存 webhook / poll 審計軌跡

#### 8.11.5 目標接口

- `POST /v1/internal/tradingagents/submit`
- `POST /v1/internal/tradingagents/job-terminal`
- `GET /v1/admin/tradingagents/analyses`
- `POST /v1/admin/tradingagents/reconcile-delayed`

#### 8.11.6 驗收標準

- TradingAgents 不可阻塞 scanner fast path。
- webhook 丟失時可由 poller 在 timeout 內補齊。
- delayed、failed、canceled 與 succeeded 狀態分離清晰。

#### 8.11.7 工單拆分

- `AI-01`：gateway client
- `AI-02`：request_id policy
- `AI-03`：analysis record repository
- `AI-04`：polling worker
- `AI-05`：webhook receiver
- `AI-06`：admin read model
- `AI-07`：delayed reconciliation tooling

### 8.12 外部資料與第三方整合

#### 8.12.1 範圍

- Yahoo Finance proxy
- Binance proxy
- SES / Resend
- Telegram
- Web Push
- Polygon / 市場資料 provider

#### 8.12.2 原則

- 第三方適配器全部放在 `infra/integrations/`。
- 所有第三方 adapter 必須有 timeout、retry、circuit breaker、provider metrics。
- 對外代理接口不得暴露未過濾參數。
- 所有 provider 秘鑰走 Secret Manager，不走 `.env` 長期保存。

#### 8.12.3 工單拆分

- `EXT-01`：Yahoo adapter
- `EXT-02`：Binance adapter
- `EXT-03`：SES / Resend adapters
- `EXT-04`：Telegram adapter
- `EXT-05`：WebPush adapter
- `EXT-06`：市場資料供應商抽象層

---

## 9. 數據與存儲改造方案

### 9.1 PostgreSQL / Citus 分層策略

300 萬 DAU 下，OLTP 仍以 PostgreSQL 為主，但必須分成三類：

1. 使用者主資料：`users`、`sessions`、`user_account`、`user_watchlist`、`user_portfolio`
2. 交易 / 通知主資料：`signals`、`trade_log`、`notifications`、`message_receipts`
3. 系統與 AI 協調資料：`tradingagents_analysis_records`、`sys_config`、`outbox_events`

### 9.2 分片鍵

建議分片鍵：

- user-centric tables：`user_id`
- notification / receipt：`user_id`
- trade_log：`user_id`
- symbol-centric aggregation：獨立 projection / analytics，不強行放 user shard

### 9.3 時間分區

保留並擴展現有策略：

- `notifications`：按月分區
- `message_receipts_archive`：按月分區
- `user_events`：按月分區
- 新增 `outbox_events`：按日或按月分區
- 新增 `scanner_decisions`：按日分區

### 9.4 ClickHouse 承接內容

ClickHouse 承接以下分析負載：

- admin overview 聚合
- signal outcome / strategy ranking 長視窗比較
- notification deliverability 看板
- receipt escalation 運營統計
- TradingAgents 成功率、延遲、provider 分析
- scanner 運行與 symbol 級別覆蓋報表

### 9.5 S3 / MinIO 承接內容

- 歷史回測結果輸出
- 大型 AI 分析原始 payload 快照
- 老分區壓縮歸檔
- 壓測報告與 run artifact

### 9.6 新增基礎表

| 表名 | 用途 |
|---|---|
| `outbox_events` | 跨域事件可靠投遞 |
| `idempotency_keys` | 命令冪等控制 |
| `subscription_snapshots` | 開始訂閱快照與審計 |
| `scanner_runs` | 每輪掃描元資料 |
| `scanner_decisions` | 策略選擇 / 抑制原因 / 證據 |
| `delivery_attempts` | provider 級投遞嘗試 |
| `admin_audit_events` | 管理行為審計 |
| `tradingagents_submit_failures` | 提交未被接受前的失敗記錄 |
| `symbol_quality_events` | 行情 / symbol 資料品質事件 |

---

## 10. API 設計規範

### 10.1 URL 與版本

- 所有新 API 統一以 `/v1/` 開頭。
- admin API 可用 `/v1/admin/` 或單獨 host，但 contract 仍版本化。

### 10.2 分頁規範

- 使用 `limit + cursor` 優先，避免大 offset。
- 與現有前端兼容期可保留 `page + limit`，但後端內部逐步轉 cursor。

### 10.3 錯誤模型

統一返回：

```json
{
  "error": {
    "code": "watchlist_limit_reached",
    "message": "Watchlist limit reached (50 symbols)",
    "request_id": "req_...",
    "details": {}
  }
}
```

### 10.4 冪等規範

以下接口強制支持 `X-Idempotency-Key`：

- `POST /v1/account/start-subscription`
- `POST /v1/watchlist`
- `POST /v1/portfolio`
- `POST /v1/trades/*`
- `POST /v1/internal/tradingagents/submit`

### 10.5 權限規範

- public API：session token scope
- internal API：service token / mTLS / internal gateway
- admin API：RBAC + scope + audit

---

## 11. 非功能改造要求

### 11.1 安全

- 所有敏感操作記錄 operator、IP、user-agent、request_id。
- admin 僅允許內網 / VPN / Zero Trust 閘道訪問。
- 第三方秘鑰統一存 Secret Manager。
- 對外 webhook 採 Bearer token 或 mTLS。
- 所有 HTML confirmation link 必須具備過期時間與簽名驗證。

### 11.2 可觀測性

- 每個 request、job、event 都必須帶 request_id 或 correlation_id。
- 每個 Kafka consumer group 都要有 lag 指標。
- 每個 worker 都要上報成功率、重試次數、DLQ 深度。

### 11.3 災備與恢復

- PostgreSQL 每日全量備份 + WAL 歸檔。
- Redis 只作緩存與短期狀態，不作唯一真相來源。
- Kafka 保留期至少 7 天，重要 topic 14 天。
- ClickHouse 與 S3 之間保留可重建鏈路。

### 11.4 兼容性

- 前端在 Phase 1 不需整頁重寫。
- 透過 BFF 或 API compatibility layer 保持舊端點一段時間可用。
- 舊 Node 系統與新 Python 系統需有雙寫與 shadow read 期。

---

## 12. 目標部署拓撲

### 12.1 基礎部署

部署建議：Kubernetes，多 AZ，同區域內部署。

### 12.2 建議初始生產規模

| 元件 | 初始 pod 數 | 自動擴展範圍 |
|---|---|---|
| `public-api` | 12 | 12 到 48 |
| `admin-api` | 4 | 4 到 12 |
| `scanner-worker` | 6 | 6 到 24 |
| `notification-orchestrator` | 4 | 4 到 16 |
| `push-dispatch-worker` | 10 | 10 到 80 |
| `email-dispatch-worker` | 4 | 4 到 20 |
| `receipt-escalation-worker` | 2 | 2 到 8 |
| `tradingagents-bridge-worker` | 2 | 2 到 12 |
| `backtest-worker` | 2 | 2 到 10 |
| `market-data-worker` | 2 | 2 到 8 |

### 12.3 自動擴展觸發指標

- public-api：CPU、RPS、P95 latency
- scanner-worker：pending symbol buckets、run lag
- push/email workers：topic lag、claim latency、DLQ depth
- tradingagents-bridge-worker：pending reconciliation rows、webhook lag

### 12.4 資料層建議

- PostgreSQL/Citus：1 coordinator + 4 worker 起步，成長到 8 worker
- Redis：3 master + 3 replica cluster
- Redpanda/Kafka：3 broker 起步，成長到 6 broker
- ClickHouse：3 shards x 2 replicas 或託管版

---

## 13. 分階段實施計畫

### Phase 0：凍結現況與基線補齊

目標：在不停止業務的前提下，補齊遷移所需契約與觀測。

交付：

- 現有 API 全量 OpenAPI 補齊
- 資料表 owner 清單
- 事件清單與缺口清單
- 壓測基線
- Node 生產路徑觀測補齊

### Phase 1：Python 基礎平台建立

目標：建立 Python monorepo、公共 infra、資料層與 deployment baseline。

交付：

- FastAPI skeleton
- SQLAlchemy + Alembic
- Redis / Kafka / ClickHouse 接入
- OpenTelemetry baseline
- CI/CD

### Phase 2：低風險域先搬遷

優先順序：

- auth
- account
- watchlist
- portfolio
- search

切流方式：

- 先 shadow read
- 再小流量寫入
- 最後全量切換舊 Node 對應路由

### Phase 3：通知與交易鏈路搬遷

優先順序：

- notifications API
- push device API
- message outbox / receipts
- trade confirmation flow
- receipt escalation worker

### Phase 4：scanner 與策略鏈路搬遷

優先順序：

- active symbols projector
- scanner shard coordinator
- signal generation
- ranking refresh / evidence pipeline
- signal -> notification orchestrator

### Phase 5：admin 與 analytics 搬遷

優先順序：

- admin overview
- distribution console
- task / receipt / retry commands
- strategy health / backtest analytics
- TradingAgents admin read model

### Phase 6：TradingAgents bridge 與全鏈路調和

交付：

- Python 版 submit / webhook / poller
- delayed jobs dashboard
- failure replay / manual reconcile tooling

### Phase 7：Node 退場與 Python 全量切流

交付：

- 舊 API 全部下線
- 舊 worker 全部停用
- 舊部署腳本淘汰
- Python 版成為唯一生產路徑

---

## 14. 團隊分工建議

| 團隊 | 責任域 | 關鍵交付 |
|---|---|---|
| 平台組 | monorepo、CI/CD、K8s、observability | Python skeleton、部署模板、告警 |
| 帳戶組 | auth、account、subscription、watchlist、portfolio | public-api 基礎域 |
| 訊號組 | active symbols、scanner、ranking、backtest、OHLCV quality | signal engine |
| 通知組 | notifications、push/email、receipt、trade flow | delivery pipeline |
| AI 整合組 | TradingAgents bridge、admin AI 視圖 | async AI integration |
| 數據組 | ClickHouse、報表、冷存、分析視圖 | analytics data plane |
| 測試組 | contract/e2e/load | 灰度與切流驗收 |

---

## 15. 開發準則

1. 所有新 Python 代碼必須使用 type hints。
2. 所有 domain service 不可在 router 內直接寫複雜 SQL。
3. 所有跨域副作用必須事件化，不允許在單個 request handler 內同步串多個外部依賴。
4. 所有讀寫 hot path 必須提供壓測腳本。
5. 所有 worker 必須可安全重啟、冪等重放。
6. 所有 admin 動作必須審計。
7. 所有 schema 改動必須附 migration、回滾腳本與兼容期說明。

---

## 16. 測試與驗收矩陣

### 16.1 測試層級

- Unit tests：domain policy、schema、repository
- Integration tests：DB、Redis、Kafka、ClickHouse、第三方 adapter
- Contract tests：OpenAPI 與 event payload
- E2E tests：登入、開始訂閱、signal、notification、trade、admin、TradingAgents
- Load tests：auth、dashboard、notifications、scanner、TradingAgents bridge

### 16.2 必測業務回歸

- 驗證碼登入與 dev fallback
- 開始訂閱快照與 `subscription.status=active`
- watchlist / portfolio 的 symbol normalization
- trade confirm / ignore / adjust
- push device 綁定 / 停用 / test
- notification read / ack
- scanner 產生 signal 後 fanout 到 notifications
- TradingAgents request_id 到 terminal result 的整條異步鏈路
- admin 對 delayed / failed 任務的觀測與重試

### 16.3 上線驗收標準

- 所有 public API 合約與舊端兼容或已完成前端切換。
- 所有 worker 在故障恢復後不丟單、不重覆寫關鍵狀態。
- 壓測到目標容量的 1.5 倍仍能維持核心 SLO。
- 至少完成 2 次灰度切流與回滾演練。

---

## 17. 主要風險與對策

### 17.1 風險：遷移期間雙寫不一致

對策：

- 所有雙寫域先從 append-only 寫入開始
- 引入 reconciliation job 與日常對賬報表

### 17.2 風險：scanner 分片後決策不一致

對策：

- 固定 symbol bucket hash 規則
- 所有 shared policy versioned
- 每輪 run 都記錄 policy version

### 17.3 風險：通知爆發壓垮資料庫

對策：

- 改為 outbox + Kafka fanout
- notifications / receipts 讀寫分離
- admin 改讀 ClickHouse

### 17.4 風險：TradingAgents 成為隱性阻塞點

對策：

- 僅允許 async submit
- poller / webhook 並行存在
- 所有 delayed / failed 狀態從 fast path 解耦

### 17.5 風險：團隊在基礎框架上反覆拉扯

對策：

- 本文已鎖定 FastAPI、SQLAlchemy async、Alembic、Redis、Kafka、ClickHouse
- 除非 CTO 級別批准，不再更換主棧

---

## 18. 最終定義的完成狀態

當以下條件全部滿足，才能視為「Stock 專案已完成 Python 化並具備 300 萬 DAU 能力」：

1. 所有 Node/TS 服務端 API 已停止承載生產流量。
2. 所有 worker、scanner、admin API、TradingAgents bridge 均由 Python 承接。
3. 前端僅透過 Python OpenAPI client 與後端通信。
4. 通知、交易、signal、TradingAgents、admin 觀測全部在 Python 路徑閉環。
5. 系統完成 300 萬 DAU 對應的讀寫、通知、scanner、AI 深度分析壓測與灰度驗收。
6. 所有 runbook、告警、備份、回滾、補償流程已文檔化並實測。

---

## 19. 啟動順序建議

若明天就要開工，按以下順序啟動：

1. 平台組先建 `stock-python` 倉庫骨架與 CI/CD。
2. 帳戶組先搬 `auth + account + watchlist + portfolio + search`。
3. 通知組同步建 `notifications + push devices + receipts + trade`。
4. 訊號組開始建 `active symbols projector + scanner sharding`。
5. AI 整合組接 `TradingAgents bridge` 與 admin read model。
6. 數據組同步搭 ClickHouse 與 outbox sink。
7. 測試組在第二週開始建立 contract / e2e / load 測試基線。

這樣做的原因是：

- 可以最早形成 Python 平台與穩定 API contract。
- 可以先搬低風險高價值域。
- 可以避免團隊一開始就卡在 scanner 或 AI 這類高複雜鏈路。

---

## 20. 附錄：現有功能對應到 Python 模塊的直接映射

| 現有能力 | Python 承接模塊 |
|---|---|
| `/api/auth/*` | `domains/auth` |
| `/api/account/*` | `domains/account` + `domains/subscription` |
| `/api/watchlist/*` | `domains/watchlist` |
| `/api/portfolio/*` | `domains/portfolio` |
| `/api/search/*` | `domains/search` |
| `/api/trade/*` | `domains/trades` |
| `/api/notifications/*` | `domains/notifications` |
| `/api/signals/desktop` | `domains/signals` |
| `/admin-api/*` | `domains/admin` |
| TradingAgents webhook / poller / repository | `domains/tradingagents` |
| scanner / backtest / ranking | `domains/signals` + `domains/analytics` |
| `/health` + `/metrics` | `infra/http` + `infra/observability` |

本映射表可作為建立 Python 目錄與分派 owner 的第一份任務清單。

---

## 21. QA 結論：本文目前如何讓新手也能直接開發

本次 QA 後，本文新增三個硬要求，避免團隊把文檔看懂了卻無法動手：

1. 每個功能域都必須有固定的 Python 文件清單，而不是只說「放到某個 domain」。
2. 每個功能域都必須有明確的類名、函數名、輸入輸出責任，避免新人自己發明命名與分層。
3. 每個功能域都必須按相同開發順序實作：`schema -> model -> repository -> service -> router/worker -> tests`。

如果任何小組提交的代碼不符合這三條，就視為沒有按本文執行。

### 21.1 新手開發禁止事項

以下事情一律不要做：

- 不要自己更換技術棧，例如把 FastAPI 改成 Django、把 Kafka 改成 RabbitMQ。
- 不要把業務邏輯直接寫在 router 內。
- 不要讓 repository 直接呼叫第三方服務。
- 不要讓 worker 直接回寫多個業務域而不經 domain service。
- 不要在沒有 Alembic migration 的情況下直接改資料庫。
- 不要跳過單元測試直接進入聯調。
- 不要在沒有 idempotency 設計時實作任何寫接口。

### 21.2 新手開發固定順序

每做一個功能，都必須按以下順序建檔與實作：

1. 在 `domains/<domain>/schemas.py` 定義請求與響應模型。
2. 在 `infra/db/models/<domain>.py` 定義 ORM model。
3. 在 `domains/<domain>/repository.py` 定義資料讀寫。
4. 在 `domains/<domain>/service.py` 定義業務流程。
5. 在 `apps/public_api/routers/` 或 `apps/admin_api/routers/` 建路由函數。
6. 如有非同步流程，在 `apps/workers/` 補對應 worker。
7. 在 `tests/unit/`、`tests/integration/`、`tests/contract/` 補測試。

### 21.3 每個功能完成的最低標準

每個功能 PR 至少必須包含：

- Pydantic schema
- ORM model 或明確復用既有 model
- repository class
- service class
- router function 或 worker entrypoint
- unit test
- integration test
- OpenAPI contract 更新
- migration 或「無需 migration」說明

---

## 22. 給小白的開工手冊

本章專門寫給第一次參與這個 Python 重構的人。照本章做，不需要自己理解整個系統才開始動手。

### 22.1 先建立的倉庫文件

先建立以下根目錄文件，沒有這些，不允許開始寫業務代碼：

```text
stock-python/
├── pyproject.toml
├── README.md
├── .env.example
├── alembic.ini
├── Makefile
├── docker-compose.local.yml
├── apps/
├── domains/
├── infra/
├── alembic/
├── tests/
└── ops/
```

### 22.2 `pyproject.toml` 最少依賴

最少依賴必須包含：

- `fastapi`
- `uvicorn`
- `gunicorn`
- `sqlalchemy`
- `asyncpg`
- `alembic`
- `pydantic`
- `pydantic-settings`
- `httpx`
- `redis`
- `aiokafka` 或團隊統一 Kafka client
- `structlog` 或團隊統一 JSON logger
- `prometheus-client`
- `opentelemetry-*`
- `pytest`
- `pytest-asyncio`
- `pytest-cov`

### 22.3 第一週的正確開發方式

第 1 天只做基礎設施：

- `Settings`
- `DB engine`
- `Session factory`
- `UnitOfWork`
- `BaseModel`
- `BaseRepository`
- `AppError`
- `RequestContext`
- `IdempotencyService`
- `OutboxPublisher`

第 2 到 3 天只做最簡單的 API 域：

- `auth`
- `account`
- `watchlist`
- `portfolio`
- `search`

第 4 到 5 天才碰通知與交易：

- `notifications`
- `push devices`
- `trades`
- `receipts`

第二週再碰複雜域：

- `scanner`
- `backtest`
- `admin analytics`
- `TradingAgents bridge`

### 22.4 每個人每天的交付順序

如果你是新人，每天只做下面這個順序：

1. 讀本文對應功能域的小節。
2. 按本文指定的文件清單把空文件先建出來。
3. 先寫 schema，再寫 ORM model，再寫 repository。
4. service class 寫完前，不要碰 router。
5. router 跑通後，先補 unit test，再補 integration test。
6. 測試過了才發 PR。

### 22.5 新人最常犯的錯

- 把查詢 SQL 寫到 router。
- 直接在 service 裡開新 DB session。
- 把 Kafka publish 放在 transaction commit 前。
- 把外部 provider 調用寫進 repository。
- router 裡直接 `try/except` 吞掉錯誤。
- 沒做 idempotency 就實作 `POST` 寫接口。
- 用同步 client 呼叫外部服務。

---

## 23. 全局文件、公共類與公共函數藍圖

這一章是整個 Python 倉庫的共同底座。所有功能域都必須復用這裡的類，不允許每個小組各寫一套。

### 23.1 全局命名規則

- schema 類一律用 `XxxRequest`、`XxxResponse`、`XxxItem`、`XxxQuery`
- repository 類一律用 `XxxRepository`
- service 類一律用 `XxxService`
- 只讀聚合服務一律用 `XxxQueryService`
- 只寫命令服務一律用 `XxxCommandService`
- 策略/規則類一律用 `XxxPolicy`
- worker 類一律用 `XxxWorker`
- 第三方客戶端一律用 `XxxClient`
- 事件發布器一律用 `XxxPublisher`
- 投影更新器一律用 `XxxProjector`

### 23.2 公共文件清單

| 文件 | 類 / 函數 | 必須提供的內容 |
|---|---|---|
| `infra/core/config.py` | `Settings`, `get_settings()` | 所有環境變量與設定集中管理 |
| `infra/core/context.py` | `RequestContext`, `build_request_context()` | request_id、user_id、ip、user_agent、trace_id |
| `infra/core/errors.py` | `AppError` 及子類 | 統一錯誤碼、message、status_code |
| `infra/core/logging.py` | `configure_logging()` | JSON 結構化日誌 |
| `infra/core/pagination.py` | `CursorPage`, `encode_cursor()`, `decode_cursor()` | 游標分頁工具 |
| `infra/security/auth.py` | `CurrentUser`, `require_user()`, `require_admin()` | public/admin 權限依賴 |
| `infra/security/token_signer.py` | `TokenSigner` | HMAC token 簽名與驗證 |
| `infra/security/idempotency.py` | `IdempotencyService` | acquire、store_result、replay |
| `infra/db/models/base.py` | `Base`, `TimestampMixin` | 所有 ORM model 的基類 |
| `infra/db/repository_base.py` | `BaseRepository` | 所有 repository 共用的 session 與 helper |
| `infra/db/session.py` | `build_engine()`, `build_session_factory()`, `get_db_session()` | Async DB session 管理 |
| `infra/db/uow.py` | `AsyncUnitOfWork` | commit、rollback、flush |
| `infra/events/outbox.py` | `OutboxEvent`, `OutboxPublisher` | 交易內寫 outbox |
| `infra/events/bus.py` | `EventBus` | publish、publish_batch |
| `infra/cache/redis_client.py` | `get_redis()` | Redis 單例客戶端 |
| `infra/cache/rate_limit.py` | `RedisRateLimiter` | hit、remaining、reset_at |
| `infra/http/http_client.py` | `HttpClientFactory` | 對外 httpx client |
| `infra/observability/metrics.py` | `MetricsRegistry` | counter、histogram、gauge |
| `infra/observability/tracing.py` | `configure_tracing()` | OTel tracing |
| `infra/storage/object_storage.py` | `ObjectStorageClient` | S3 / MinIO 上傳下載 |
| `apps/admin_api/dependencies.py` | `get_*_service()` | admin API 的依賴注入組裝 |

### 23.3 公共類的最低方法定義

#### `Settings`

必須至少包含：

- `app_env`
- `app_name`
- `public_api_host`
- `public_api_port`
- `admin_api_host`
- `admin_api_port`
- `database_url`
- `redis_url`
- `kafka_bootstrap_servers`
- `clickhouse_dsn`
- `secret_key`
- `internal_service_token`
- `tradingagents_base_url`
- `tradingagents_auth_token`

#### `RequestContext`

必須至少包含：

- `request_id`
- `trace_id`
- `user_id`
- `operator_id`
- `ip`
- `user_agent`
- `locale`
- `timezone`

#### `AppError` 及子類

至少定義以下錯誤類：

- `ValidationError`
- `UnauthorizedError`
- `ForbiddenError`
- `NotFoundError`
- `ConflictError`
- `RateLimitError`
- `ExternalServiceError`
- `DomainRuleError`

#### `AsyncUnitOfWork`

必須有以下方法：

- `__aenter__`
- `__aexit__`
- `commit()`
- `rollback()`
- `flush()`

#### `BaseRepository`

必須至少包含：

- `session` 屬性
- `add(instance)`
- `delete(instance)`
- `flush()`
- `refresh(instance)`

所有具體 repository 都繼承它，避免每個人各自複製 session 操作。

#### `OutboxPublisher`

必須有以下方法：

- `publish_after_commit(event_name, payload, aggregate_id, aggregate_type)`
- `publish_batch_after_commit(events)`

### 23.4 全局標準模板

#### repository 標準模板

```python
class ExampleRepository:
  def __init__(self, session: AsyncSession) -> None:
    self.session = session

  async def get_by_id(self, object_id: UUID) -> ExampleModel | None:
    ...

  async def create(self, data: dict) -> ExampleModel:
    ...

  async def update(self, object_id: UUID, data: dict) -> ExampleModel:
    ...
```

#### service 標準模板

```python
class ExampleService:
  def __init__(
    self,
    repository: ExampleRepository,
    outbox_publisher: OutboxPublisher,
  ) -> None:
    self.repository = repository
    self.outbox_publisher = outbox_publisher

  async def execute(self, ctx: RequestContext, req: ExampleRequest) -> ExampleResponse:
    ...
```

#### router 標準模板

```python
router = APIRouter(prefix="/v1/examples", tags=["examples"])

@router.post("", response_model=ExampleResponse)
async def create_example(
  payload: ExampleRequest,
  ctx: RequestContext = Depends(build_request_context),
  service: ExampleService = Depends(get_example_service),
) -> ExampleResponse:
  return await service.execute(ctx, payload)
```

#### dependency provider 標準模板

```python
def get_example_service(
  session: AsyncSession = Depends(get_db_session),
  event_bus: EventBus = Depends(get_event_bus),
) -> ExampleService:
  repository = ExampleRepository(session)
  outbox_publisher = OutboxPublisher(session, event_bus)
  return ExampleService(repository, outbox_publisher)
```

---

## 24. 逐功能文件、類、函數的最終實作藍圖

本章是本文最重要的施工圖。所有開發都按這裡的文件和類名落地，不允許自由發揮。

### 24.1 Auth 域

#### 24.1.1 必建文件

```text
infra/db/models/auth.py
domains/auth/schemas.py
domains/auth/repository.py
domains/auth/policies.py
domains/auth/service.py
apps/public_api/routers/auth.py
tests/unit/auth/test_auth_service.py
tests/integration/auth/test_auth_router.py
tests/contract/test_auth_openapi.py
```

#### 24.1.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/auth.py` | `UserModel` | 對應 `users` |
| `infra/db/models/auth.py` | `EmailCodeModel` | 對應 `email_codes` |
| `infra/db/models/auth.py` | `SessionModel` | 對應 `sessions` |
| `domains/auth/schemas.py` | `SendCodeRequest` | `email` |
| `domains/auth/schemas.py` | `VerifyCodeRequest` | `email`, `code`, `locale`, `timezone` |
| `domains/auth/schemas.py` | `RefreshTokenRequest` | `refresh_token` |
| `domains/auth/schemas.py` | `AuthUserResponse` | `id`, `email`, `plan`, `locale`, `timezone`, `is_new` |
| `domains/auth/schemas.py` | `AuthSessionResponse` | `access_token`, `refresh_token`, `user` |
| `domains/auth/repository.py` | `UserRepository` | `get_by_email()`, `get_by_id()`, `upsert_by_email()`, `update_last_login()` |
| `domains/auth/repository.py` | `EmailCodeRepository` | `create_code()`, `find_valid_code()`, `mark_used()`, `delete_expired()` |
| `domains/auth/repository.py` | `SessionRepository` | `create_session()`, `get_by_token_hash()`, `revoke_by_token_hash()`, `rotate_refresh_session()` |
| `domains/auth/policies.py` | `AuthPolicy` | `can_return_dev_code()`, `validate_send_code_limit()`, `validate_verify_code_limit()`, `is_new_user()` |
| `domains/auth/service.py` | `AuthService` | `send_code()`, `verify_code()`, `logout()`, `refresh()` |
| `apps/public_api/routers/auth.py` | `send_code()` | `POST /v1/auth/send-code` |
| `apps/public_api/routers/auth.py` | `verify_code()` | `POST /v1/auth/verify` |
| `apps/public_api/routers/auth.py` | `logout()` | `POST /v1/auth/logout` |
| `apps/public_api/routers/auth.py` | `refresh()` | `POST /v1/auth/refresh` |

#### 24.1.3 開發順序

1. 先建 `SendCodeRequest`、`VerifyCodeRequest`。
2. 再建三個 repository。
3. `AuthService.send_code()` 只負責驗證、生成 code、存儲、呼叫 email adapter。
4. `AuthService.verify_code()` 只負責驗證 code、upsert user、建立 session。
5. router 不允許直接存 DB。

### 24.2 Account 與 Subscription 域

#### 24.2.1 必建文件

```text
infra/db/models/account.py
domains/account/schemas.py
domains/account/repository.py
domains/account/service.py
domains/subscription/schemas.py
domains/subscription/policies.py
domains/subscription/repository.py
domains/subscription/service.py
apps/public_api/routers/account.py
tests/unit/account/test_account_service.py
tests/unit/subscription/test_start_subscription_service.py
tests/integration/account/test_account_router.py
```

#### 24.2.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/account.py` | `UserAccountModel` | 對應 `user_account` |
| `infra/db/models/account.py` | `SubscriptionSnapshotModel` | 對應 `subscription_snapshots` |
| `domains/account/schemas.py` | `UpdateAccountRequest` | `name`, `locale`, `timezone`, `total_capital`, `currency` |
| `domains/account/schemas.py` | `AccountDashboardResponse` | `user`, `account`, `portfolio`, `watchlist`, `subscription` |
| `domains/subscription/schemas.py` | `StartSubscriptionRequest` | `account`, `watchlist`, `portfolio`, `allow_empty_portfolio` |
| `domains/account/repository.py` | `AccountRepository` | `get_profile()`, `get_dashboard()`, `upsert_account()`, `update_user_profile()` |
| `domains/subscription/repository.py` | `SubscriptionRepository` | `save_snapshot()`, `update_user_subscription_extra()`, `load_subscription_summary()` |
| `domains/subscription/policies.py` | `SubscriptionPolicy` | `build_state()`, `validate_start_request()`, `enforce_watchlist_limit()`, `enforce_portfolio_limit()` |
| `domains/account/service.py` | `AccountService` | `get_profile()`, `get_dashboard()`, `update_profile()` |
| `domains/subscription/service.py` | `StartSubscriptionService` | `start_subscription()` |
| `apps/public_api/routers/account.py` | `get_profile()` | `GET /v1/account/profile` |
| `apps/public_api/routers/account.py` | `get_dashboard()` | `GET /v1/account/dashboard` |
| `apps/public_api/routers/account.py` | `update_profile()` | `PUT /v1/account/profile` |
| `apps/public_api/routers/account.py` | `start_subscription()` | `POST /v1/account/start-subscription` |

#### 24.2.3 `StartSubscriptionService.start_subscription()` 必做步驟

1. 讀 user 與當前 summary。
2. 規範化 watchlist / portfolio symbol。
3. 驗證 total capital、watchlist、portfolio 與 plan limit。
4. 更新 `users.extra.subscription`。
5. 寫 `subscription_snapshots`。
6. 寫 outbox：`account.subscription.started`。
7. 返回最新 dashboard。

### 24.3 Watchlist 域

#### 24.3.1 必建文件

```text
infra/db/models/watchlist.py
domains/watchlist/schemas.py
domains/watchlist/repository.py
domains/watchlist/service.py
domains/watchlist/policies.py
apps/public_api/routers/watchlist.py
tests/unit/watchlist/test_watchlist_service.py
tests/integration/watchlist/test_watchlist_router.py
```

#### 24.3.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/watchlist.py` | `WatchlistItemModel` | 對應 `user_watchlist` |
| `domains/watchlist/schemas.py` | `CreateWatchlistRequest` | `symbol`, `notify`, `min_score` |
| `domains/watchlist/schemas.py` | `UpdateWatchlistRequest` | `notify`, `min_score` |
| `domains/watchlist/schemas.py` | `WatchlistItemResponse` | `id`, `symbol`, `notify`, `min_score`, `created_at` |
| `domains/watchlist/repository.py` | `WatchlistRepository` | `list_by_user()`, `get_by_id()`, `get_by_user_and_symbol()`, `create()`, `update()`, `delete()` |
| `domains/watchlist/policies.py` | `WatchlistPolicy` | `normalize_symbol()`, `validate_min_score()`, `enforce_plan_limit()` |
| `domains/watchlist/service.py` | `WatchlistService` | `list_items()`, `add_item()`, `update_item()`, `delete_item()` |
| `apps/public_api/routers/watchlist.py` | `list_watchlist()` | `GET /v1/watchlist` |
| `apps/public_api/routers/watchlist.py` | `create_watchlist_item()` | `POST /v1/watchlist` |
| `apps/public_api/routers/watchlist.py` | `update_watchlist_item()` | `PUT /v1/watchlist/{id}` |
| `apps/public_api/routers/watchlist.py` | `delete_watchlist_item()` | `DELETE /v1/watchlist/{id}` |

### 24.4 Portfolio 域

#### 24.4.1 必建文件

```text
infra/db/models/portfolio.py
domains/portfolio/schemas.py
domains/portfolio/repository.py
domains/portfolio/service.py
domains/portfolio/policies.py
apps/public_api/routers/portfolio.py
tests/unit/portfolio/test_portfolio_service.py
tests/integration/portfolio/test_portfolio_router.py
```

#### 24.4.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/portfolio.py` | `PortfolioPositionModel` | 對應 `user_portfolio` |
| `domains/portfolio/schemas.py` | `CreatePortfolioRequest` | `symbol`, `shares`, `avg_cost`, `total_capital`, `target_profit`, `stop_loss`, `notify`, `notes` |
| `domains/portfolio/schemas.py` | `UpdatePortfolioRequest` | 同上但可選 |
| `domains/portfolio/repository.py` | `PortfolioRepository` | `list_by_user()`, `get_by_id()`, `get_by_user_and_symbol()`, `create()`, `update()`, `delete()`, `upsert_from_trade()` |
| `domains/portfolio/policies.py` | `PortfolioPolicy` | `normalize_symbol()`, `validate_numbers()`, `enforce_plan_limit()` |
| `domains/portfolio/service.py` | `PortfolioService` | `list_positions()`, `add_position()`, `update_position()`, `delete_position()` |
| `apps/public_api/routers/portfolio.py` | `list_portfolio()` | `GET /v1/portfolio` |
| `apps/public_api/routers/portfolio.py` | `create_position()` | `POST /v1/portfolio` |
| `apps/public_api/routers/portfolio.py` | `update_position()` | `PUT /v1/portfolio/{id}` |
| `apps/public_api/routers/portfolio.py` | `delete_position()` | `DELETE /v1/portfolio/{id}` |

### 24.5 Search 域

#### 24.5.1 必建文件

```text
infra/db/models/symbols.py
domains/search/schemas.py
domains/search/repository.py
domains/search/service.py
apps/public_api/routers/search.py
tests/unit/search/test_search_service.py
tests/integration/search/test_search_router.py
```

#### 24.5.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/symbols.py` | `SymbolModel` | 對應 `symbols` |
| `domains/search/schemas.py` | `SearchSymbolsQuery` | `q`, `limit`, `cursor` |
| `domains/search/schemas.py` | `SymbolSearchItem` | `symbol`, `name`, `exchange`, `asset_type` |
| `domains/search/repository.py` | `SearchRepository` | `search_symbols()`, `get_symbol_by_code()` |
| `domains/search/service.py` | `SearchService` | `search_symbols()` |
| `apps/public_api/routers/search.py` | `search_symbols()` | `GET /v1/search/symbols` |

### 24.6 Trades 域

#### 24.6.1 必建文件

```text
infra/db/models/trades.py
domains/trades/schemas.py
domains/trades/repository.py
domains/trades/link_security.py
domains/trades/service.py
domains/trades/html_renderer.py
apps/public_api/routers/trades.py
tests/unit/trades/test_trade_service.py
tests/integration/trades/test_trade_router.py
```

#### 24.6.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/trades.py` | `TradeLogModel` | 對應 `trade_log` |
| `domains/trades/schemas.py` | `AdjustTradeRequest` | `actual_shares`, `actual_price` |
| `domains/trades/schemas.py` | `TradeInfoResponse` | `trade`, `is_expired`, `expires_at` |
| `domains/trades/repository.py` | `TradeRepository` | `get_by_id()`, `get_by_id_for_user()`, `update_status()`, `record_execution()`, `mark_ignored()` |
| `domains/trades/link_security.py` | `TradeLinkSigner` | `sign()`, `verify()`, `is_expired()` |
| `domains/trades/html_renderer.py` | `TradeHtmlRenderer` | `render_status_page()`, `render_confirm_page()` |
| `domains/trades/service.py` | `TradeService` | `get_public_info()`, `get_app_info()`, `confirm_trade()`, `ignore_trade()`, `adjust_trade()`, `acknowledge_trade_receipts()` |
| `apps/public_api/routers/trades.py` | `get_trade_info()` | `GET /v1/trades/{id}/info` |
| `apps/public_api/routers/trades.py` | `get_trade_app_info()` | `GET /v1/trades/{id}/app-info` |
| `apps/public_api/routers/trades.py` | `confirm_trade()` | `POST /v1/trades/{id}/confirm` |
| `apps/public_api/routers/trades.py` | `ignore_trade()` | `POST /v1/trades/{id}/ignore` |
| `apps/public_api/routers/trades.py` | `adjust_trade()` | `POST /v1/trades/{id}/adjust` |
| `apps/public_api/routers/trades.py` | `app_confirm_trade()` | `POST /v1/trades/{id}/app-confirm` |
| `apps/public_api/routers/trades.py` | `app_ignore_trade()` | `POST /v1/trades/{id}/app-ignore` |
| `apps/public_api/routers/trades.py` | `app_adjust_trade()` | `POST /v1/trades/{id}/app-adjust` |

### 24.7 Notifications 域

#### 24.7.1 必建文件

```text
infra/db/models/notifications.py
domains/notifications/schemas.py
domains/notifications/repository.py
domains/notifications/query_service.py
domains/notifications/command_service.py
domains/notifications/push_service.py
domains/notifications/receipt_service.py
apps/public_api/routers/notifications.py
apps/workers/notification_orchestrator/worker.py
apps/workers/push_dispatch/worker.py
apps/workers/email_dispatch/worker.py
apps/workers/receipt_escalation/worker.py
tests/unit/notifications/
tests/integration/notifications/
```

#### 24.7.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/notifications.py` | `NotificationModel` | 對應 `notifications` |
| `infra/db/models/notifications.py` | `PushSubscriptionModel` | 對應 `push_subscriptions` |
| `infra/db/models/notifications.py` | `MessageOutboxModel` | 對應 `message_outbox` |
| `infra/db/models/notifications.py` | `MessageReceiptModel` | 對應 `message_receipts` |
| `infra/db/models/notifications.py` | `DeliveryAttemptModel` | 對應 `delivery_attempts` |
| `domains/notifications/schemas.py` | `NotificationListQuery` | `cursor`, `limit` |
| `domains/notifications/schemas.py` | `RegisterPushDeviceRequest` | `device_id`, `endpoint`, `provider`, `public_key`, `auth_key`, `user_agent`, `locale`, `timezone` |
| `domains/notifications/repository.py` | `NotificationRepository` | `list_page()`, `mark_read()`, `mark_all_read()`, `bulk_create()` |
| `domains/notifications/repository.py` | `PushSubscriptionRepository` | `list_active_devices()`, `upsert_device()`, `disable_device()`, `get_device()` |
| `domains/notifications/repository.py` | `ReceiptRepository` | `create_receipt()`, `mark_opened()`, `acknowledge()`, `list_overdue_receipts()` |
| `domains/notifications/repository.py` | `DeliveryAttemptRepository` | `record_attempt()`, `mark_success()`, `mark_failure()` |
| `domains/notifications/query_service.py` | `NotificationQueryService` | `list_notifications()`, `list_push_devices()` |
| `domains/notifications/command_service.py` | `NotificationCommandService` | `mark_read()`, `mark_all_read()`, `acknowledge()` |
| `domains/notifications/push_service.py` | `PushSubscriptionService` | `register_device()`, `disable_device()`, `send_test_push()` |
| `domains/notifications/receipt_service.py` | `ReceiptEscalationService` | `scan_and_escalate()` |
| `apps/public_api/routers/notifications.py` | `list_notifications()` | `GET /v1/notifications` |
| `apps/public_api/routers/notifications.py` | `list_push_devices()` | `GET /v1/notifications/push-devices` |
| `apps/public_api/routers/notifications.py` | `register_push_device()` | `POST /v1/notifications/push-devices` |
| `apps/public_api/routers/notifications.py` | `disable_push_device()` | `DELETE /v1/notifications/push-devices/{device_id}` |
| `apps/public_api/routers/notifications.py` | `test_push_device()` | `POST /v1/notifications/push-devices/{device_id}/test` |
| `apps/public_api/routers/notifications.py` | `mark_all_read()` | `PUT /v1/notifications/read-all` |
| `apps/public_api/routers/notifications.py` | `mark_read()` | `PUT /v1/notifications/{id}/read` |
| `apps/public_api/routers/notifications.py` | `acknowledge()` | `PUT /v1/notifications/{id}/ack` |
| `apps/workers/notification_orchestrator/worker.py` | `NotificationOrchestratorWorker` | `run_forever()`, `handle_signal_generated()` |
| `apps/workers/push_dispatch/worker.py` | `PushDispatchWorker` | `run_forever()`, `handle_notification_requested()`, `deliver_push()` |
| `apps/workers/email_dispatch/worker.py` | `EmailDispatchWorker` | `run_forever()`, `handle_notification_requested()`, `deliver_email()` |
| `apps/workers/receipt_escalation/worker.py` | `ReceiptEscalationWorker` | `run_forever()`, `scan_overdue_receipts()`, `escalate_receipt()` |

### 24.8 Signal Ingest、Signals、Scanner 與 Backtest 域

#### 24.8.1 必建文件

```text
infra/db/models/signals.py
domains/signals/schemas.py
domains/signals/repository.py
domains/signals/live_strategy_engine.py
domains/signals/desktop_signal_service.py
domains/signals/dedupe_policy.py
domains/signals/active_symbols_service.py
domains/market_data/repository.py
domains/analytics/backtest/repository.py
domains/analytics/backtest/service.py
apps/admin_api/routers/anomalies.py
apps/admin_api/routers/backtests.py
apps/admin_api/routers/signal_stats.py
apps/admin_api/routers/scanner.py
apps/public_api/routers/signal_ingest.py
apps/workers/scanner/worker.py
apps/workers/backtest/worker.py
tests/unit/signals/
tests/integration/signals/
```

#### 24.8.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/signals.py` | `SignalModel` | 對應 `signals` |
| `infra/db/models/signals.py` | `ScannerRunModel` | 對應 `scanner_runs` |
| `infra/db/models/signals.py` | `ScannerDecisionModel` | 對應 `scanner_decisions` |
| `domains/signals/schemas.py` | `DesktopSignalRequest` | `source`, `emitted_at`, `alert`, `analysis` |
| `domains/signals/repository.py` | `SignalRepository` | `create_signal()`, `find_recent_duplicate()`, `list_recent_by_symbol()`, `list_admin_signals()`, `summarize_admin_signals()` |
| `domains/signals/repository.py` | `ScannerRunRepository` | `create_run()`, `finish_run()`, `create_decision()`, `list_runs()`, `get_run()`, `list_decisions()` |
| `domains/signals/live_strategy_engine.py` | `LiveStrategyEngine` | `select_strategy()`, `build_signal_candidate()`, `score_candidate()` |
| `domains/signals/desktop_signal_service.py` | `DesktopSignalService` | `ingest_desktop_signal()`, `route_signal()` |
| `domains/signals/dedupe_policy.py` | `SignalDedupePolicy` | `should_suppress()`, `build_dedupe_key()` |
| `domains/signals/active_symbols_service.py` | `ActiveSymbolsService` | `refresh_projection()`, `list_scan_buckets()`, `mark_symbol_dirty()` |
| `domains/market_data/repository.py` | `OhlcvRepository` | `bulk_upsert_bars()`, `quarantine_bad_rows()`, `get_recent_bars()`, `list_anomalies()` |
| `domains/analytics/backtest/repository.py` | `BacktestRepository` | `save_run()`, `save_results()`, `save_rankings()`, `list_runs()`, `get_run()`, `list_latest_rankings()` |
| `domains/analytics/backtest/service.py` | `BacktestService` | `refresh_rankings()`, `run_backtest_window()`, `calculate_degradation()` |
| `apps/admin_api/routers/anomalies.py` | `list_ohlcv_anomalies()` | `GET /v1/admin/anomalies/ohlcv` |
| `apps/admin_api/routers/backtests.py` | `list_runs()` / `get_run()` / `create_run()` | `GET /v1/admin/backtests/runs`, `GET /v1/admin/backtests/runs/{run_id}`, `POST /v1/admin/backtests/runs` |
| `apps/admin_api/routers/signal_stats.py` | `get_signal_stats_summary()` / `list_signal_stats()` | `GET /v1/admin/signal-stats/summary`, `GET /v1/admin/signal-stats` |
| `apps/admin_api/routers/scanner.py` | `get_observability()` / `get_run()` / `list_live_decisions()` | `GET /v1/admin/scanner/observability`, `GET /v1/admin/scanner/runs/{run_id}`, `GET /v1/admin/scanner/live-decision` |
| `apps/public_api/routers/signal_ingest.py` | `ingest_desktop_signal()` | `POST /v1/internal/signals/desktop` |
| `apps/workers/scanner/worker.py` | `ScannerWorker` | `run_forever()`, `run_once()`, `process_bucket()`, `process_symbol()` |
| `apps/workers/backtest/worker.py` | `BacktestWorker` | `run_forever()`, `refresh_rankings()` |

### 24.9 Admin 域

#### 24.9.1 必建文件

```text
infra/db/models/admin.py
domains/admin/schemas.py
domains/admin/overview_service.py
domains/admin/users_service.py
domains/admin/tasks_service.py
domains/admin/distribution_service.py
domains/admin/analytics_service.py
domains/admin/system_config_service.py
domains/admin/audit_service.py
apps/admin_api/routers/overview.py
apps/admin_api/routers/users.py
apps/admin_api/routers/tasks.py
apps/admin_api/routers/distribution.py
apps/admin_api/routers/anomalies.py
apps/admin_api/routers/analytics.py
apps/admin_api/routers/backtests.py
apps/admin_api/routers/scanner.py
apps/admin_api/routers/signal_stats.py
apps/admin_api/routers/runtime_monitoring.py
apps/admin_api/routers/tradingagents.py
apps/admin_api/routers/system.py
tests/unit/admin/
tests/integration/admin/
```

#### 24.9.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/admin.py` | `AdminAuditEventModel` | 對應 `admin_audit_events` |
| `domains/admin/schemas.py` | `AdminOverviewResponse` | overview 所需聚合字段 |
| `domains/admin/overview_service.py` | `AdminOverviewService` | `get_dashboard()` |
| `domains/admin/users_service.py` | `AdminUsersService` | `search_users()`, `get_user_detail()`, `disable_user()`, `update_plan()` |
| `domains/admin/tasks_service.py` | `AdminTasksService` | `list_tasks()`, `claim_task()`, `retry_task()`, `expire_task()`, `resolve_task()` |
| `domains/admin/distribution_service.py` | `AdminDistributionService` | `get_distribution_summary()`, `get_outbox_view()`, `get_receipts_view()` |
| `domains/admin/analytics_service.py` | `AdminAnalyticsService` | `get_strategy_health()`, `get_backtest_summary()`, `get_runtime_metrics()` |
| `domains/admin/system_config_service.py` | `SystemConfigService` | `get_config()`, `update_config()` |
| `domains/admin/audit_service.py` | `AdminAuditService` | `record_action()` |
| `apps/admin_api/routers/overview.py` | `get_overview()` | `GET /v1/admin/overview` |
| `apps/admin_api/routers/users.py` | `search_users()` | `GET /v1/admin/users` |
| `apps/admin_api/routers/tasks.py` | `list_tasks()` | `GET /v1/admin/tasks` |
| `apps/admin_api/routers/tasks.py` | `claim_task()` | `POST /v1/admin/tasks/{id}/claim` |
| `apps/admin_api/routers/tasks.py` | `retry_task()` | `POST /v1/admin/tasks/{id}/retry` |
| `apps/admin_api/routers/anomalies.py` | `list_ohlcv_anomalies()` | `GET /v1/admin/anomalies/ohlcv` |
| `apps/admin_api/routers/distribution.py` | `get_distribution()` | `GET /v1/admin/distribution` |
| `apps/admin_api/routers/backtests.py` | `list_runs()` / `create_run()` | `GET /v1/admin/backtests/runs`, `POST /v1/admin/backtests/runs` |
| `apps/admin_api/routers/scanner.py` | `get_observability()` / `list_live_decisions()` | `GET /v1/admin/scanner/observability`, `GET /v1/admin/scanner/live-decision` |
| `apps/admin_api/routers/signal_stats.py` | `get_signal_stats_summary()` / `list_signal_stats()` | `GET /v1/admin/signal-stats/summary`, `GET /v1/admin/signal-stats` |
| `apps/admin_api/routers/runtime_monitoring.py` | `list_components()` | `GET /v1/admin/runtime/components` |
| `apps/admin_api/routers/tradingagents.py` | `list_analyses()` | `GET /v1/admin/tradingagents/analyses` |
| `apps/admin_api/routers/system.py` | `get_system_config()` | `GET /v1/admin/system/config` |
| `apps/admin_api/routers/system.py` | `update_system_config()` | `PUT /v1/admin/system/config` |

### 24.10 TradingAgents 域

#### 24.10.1 必建文件

```text
infra/db/models/tradingagents.py
domains/tradingagents/schemas.py
domains/tradingagents/repository.py
domains/tradingagents/gateway.py
domains/tradingagents/request_id.py
domains/tradingagents/orchestrator.py
domains/tradingagents/projection_mapper.py
domains/tradingagents/webhook_service.py
apps/public_api/routers/tradingagents_webhook.py
apps/workers/tradingagents_bridge/worker.py
apps/admin_api/routers/tradingagents.py
tests/unit/tradingagents/
tests/integration/tradingagents/
```

#### 24.10.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/tradingagents.py` | `TradingAgentsAnalysisRecordModel` | 對應 `tradingagents_analysis_records` |
| `infra/db/models/tradingagents.py` | `TradingAgentsSubmitFailureModel` | 對應 `tradingagents_submit_failures` |
| `domains/tradingagents/schemas.py` | `SubmitTradingAgentsRequest` | `request_id`, `ticker`, `analysis_date`, `selected_analysts`, `trigger_type`, `trigger_context` |
| `domains/tradingagents/schemas.py` | `TradingAgentsProjection` | `request_id`, `job_id`, `tradingagents_status`, `final_action`, `decision_summary`, `result_payload` |
| `domains/tradingagents/repository.py` | `TradingAgentsRepository` | `insert_accepted()`, `update_projection()`, `list_pending()`, `mark_delayed()`, `record_submit_failure()` |
| `domains/tradingagents/gateway.py` | `TradingAgentsGateway` | `submit_job()`, `get_stock_result()`, `build_headers()` |
| `domains/tradingagents/request_id.py` | `RequestIdBuilder` | `build()` |
| `domains/tradingagents/orchestrator.py` | `TradingAgentsOrchestrator` | `submit_from_scanner()`, `submit_manual()`, `submit_position_review()` |
| `domains/tradingagents/projection_mapper.py` | `TradingAgentsProjectionMapper` | `from_webhook_payload()`, `from_poll_response()` |
| `domains/tradingagents/webhook_service.py` | `TradingAgentsWebhookService` | `handle_terminal_event()` |
| `apps/public_api/routers/tradingagents_webhook.py` | `receive_terminal_event()` | `POST /v1/internal/tradingagents/job-terminal` |
| `apps/workers/tradingagents_bridge/worker.py` | `TradingAgentsPollingWorker` | `run_forever()`, `poll_once()`, `process_record()` |
| `apps/admin_api/routers/tradingagents.py` | `list_analyses()` | `GET /v1/admin/tradingagents/analyses` |
| `apps/admin_api/routers/tradingagents.py` | `reconcile_delayed()` | `POST /v1/admin/tradingagents/reconcile-delayed` |

### 24.11 Market Data 域

#### 24.11.1 必建文件

```text
infra/db/models/market_data.py
domains/market_data/schemas.py
domains/market_data/repository.py
domains/market_data/symbol_sync_service.py
domains/market_data/ohlcv_import_service.py
domains/market_data/quality_service.py
apps/workers/market_data/worker.py
tests/unit/market_data/
tests/integration/market_data/
```

#### 24.11.2 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/market_data.py` | `SymbolModel` | 對應 `symbols` |
| `infra/db/models/market_data.py` | `OhlcvModel` | 對應 `ohlcv` |
| `infra/db/models/market_data.py` | `OhlcvAnomalyModel` | 對應 `ohlcv_anomalies` |
| `domains/market_data/repository.py` | `SymbolRepository` | `bulk_upsert_symbols()`, `get_symbol()` |
| `domains/market_data/repository.py` | `OhlcvRepository` | `bulk_upsert_bars()`, `quarantine_bad_rows()`, `get_recent_bars()` |
| `domains/market_data/symbol_sync_service.py` | `SymbolSyncService` | `sync_symbols()` |
| `domains/market_data/ohlcv_import_service.py` | `OhlcvImportService` | `import_batch()`, `normalize_bar()` |
| `domains/market_data/quality_service.py` | `OhlcvQualityService` | `validate_batch()`, `emit_quality_event()` |
| `apps/workers/market_data/worker.py` | `MarketDataWorker` | `run_forever()`, `sync_symbols()`, `import_ohlcv()`, `run_quality_checks()` |

### 24.12 Monitoring、Health 與事件運行現況

#### 24.12.1 現有文件

```text
infra/http/health.py
infra/observability/metrics.py
infra/events/bus.py
infra/events/bootstrap.py
apps/public_api/main.py
apps/admin_api/main.py
apps/scheduler/main.py
```

#### 24.12.2 類與函數清單

| 文件 | 類 / 函數 | 現況 |
|---|---|---|
| `infra/http/health.py` | `health_check()` | `GET /health` |
| `infra/http/health.py` | `readiness_check()` | `GET /health/ready` |
| `infra/http/health.py` | `liveness_check()` | `GET /health/live` |
| `infra/observability/metrics.py` | `MetricsRegistry` | in-memory counter / gauge / histogram |
| `infra/events/bus.py` | `EventBus` | in-process publish / subscribe |
| `infra/events/bootstrap.py` | `register_default_subscribers()` | wiring analytics / notification / dispatch workers |
| `apps/public_api/main.py` | `metrics_endpoint()` | `GET /metrics` |
| `apps/admin_api/main.py` | `metrics_endpoint()` | `GET /metrics` |
| `apps/scheduler/main.py` | `build_scheduler()` | scheduler heartbeat |

---

## 25. 每個功能域的開發完成定義（DoD）

### 25.1 一個域可以合併 PR 的條件

一個功能域只有在以下條件都滿足時才能合併：

1. 文件已按本文要求建立齊全。
2. 類名與函數名符合本文，不自行改名。
3. OpenAPI 與 schema 已生成且可被前端 client 使用。
4. 單元測試與整合測試都通過。
5. 涉及寫操作的接口已具備 idempotency。
6. 涉及事件的服務已具備 outbox 寫入。
7. 涉及第三方的調用已具備 timeout、retry、metrics。
8. migration 已提供升級與回滾腳本。

### 25.2 一個新人可以獨立做的最小任務包

新人的任務要切成「最多一個 router + 一個 service + 一個 repository + 一組測試」的大小，例如：

- 新人任務 A：`auth/send-code`
- 新人任務 B：`account/profile read`
- 新人任務 C：`watchlist create`
- 新人任務 D：`portfolio update`
- 新人任務 E：`notifications mark read`

不要把以下任務直接給新人單獨承擔：

- scanner 全量重構
- notification orchestrator 全鏈路
- TradingAgents bridge 全鏈路
- admin analytics 全量 read model

### 25.3 帶教方式

如果團隊中有新手，帶教應按以下方式進行：

1. 先讓他照 `auth` 域做一個完整功能。
2. 再做 `watchlist` 或 `portfolio` 這種單域 CRUD。
3. 再做 `notifications` 裡的單個命令，例如 `mark_read`。
4. 最後才碰 trade、scanner、worker、TradingAgents。

---

## 26. 給項目負責人的落地建議

如果你要把本文真的變成可以執行的團隊工程，請立刻做以下事情：

1. 指定一個人負責 `infra/`，其他組不得自行發明公共基礎類。
2. 指定一個人負責 OpenAPI 契約治理。
3. 把第 24 章直接拆成 Jira 或 Linear 任務。
4. 先建 `auth` 域完整樣板，作為全倉庫的示範實作。
5. 所有後續域都照 `auth` 樣板複製，不再重設分層。

這樣才是真正能讓小白照著文件開發，而不是看完文檔仍然不知道第一個 Python 文件該建在哪裡。