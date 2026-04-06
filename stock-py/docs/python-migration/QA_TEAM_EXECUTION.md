# 測試組執行手冊

> 狀態（2026-04-04）：當前倉庫已落地 unit 測試、`tests/helpers/`、`tests/contract/`、auth / subscription / notification / trade / scanner / TradingAgents 的 app-level e2e smoke tests、`tests/load/`、`tests/integration/account/`、`tests/integration/analytics/`、`tests/integration/notifications/`、`tests/integration/trades/`、`tests/integration/tradingagents/`、`ops/runbooks/qa-cutover-checklist.md`，以及 `.github/workflows/qa.yml` 上的 `make lint` + `make qa-ci` 自動驗證；剩餘工作集中在 staging baseline 與切流演練留痕。

## 1. 目標

測試組負責把 Python 重構從「能跑」變成「可驗證、可灰度、可回滾」。

## 2. 當前已落地

目前倉庫中已存在的測試目錄：

```text
tests/unit/analytics/
tests/unit/account/
tests/unit/auth/
tests/unit/backtest/
tests/unit/market_data/
tests/unit/notifications/
tests/unit/portfolio/
tests/unit/search/
tests/unit/signals/
tests/unit/subscription/
tests/unit/tradingagents/
tests/unit/trades/
tests/unit/watchlist/
tests/helpers/
tests/contract/
tests/e2e/
tests/integration/account/
tests/integration/analytics/
tests/integration/notifications/
tests/integration/trades/
tests/integration/tradingagents/
```

說明：

- 目前已經有 `tests/helpers/` 與 `tests/contract/`。
- 目前已經有 `tests/e2e/test_auth_flow.py`、`tests/e2e/test_subscription_flow.py`、`tests/e2e/test_notification_flow.py`、`tests/e2e/test_trade_flow.py`、`tests/e2e/test_scanner_flow.py`、`tests/e2e/test_tradingagents_flow.py`。
- 目前已經有 `tests/integration/account/test_account_router.py`、`tests/integration/analytics/test_admin_analytics_pipeline.py`、`tests/integration/notifications/test_notifications_router.py`、`tests/integration/trades/test_trades_router.py` 與 `tests/integration/tradingagents/test_admin_tradingagents_router.py`。
- 目前已經有 `tests/load/locustfile.py` 與 `tests/load/scenarios/`。
- 目前已經有 `tests/load/validate_env.py`、`make test-qa`、`make load-report-init`、`make load-baseline`、`make cutover-report-init`、`make cutover-openapi-diff` 等 QA / cutover 入口。
- 目前已經有 `ops/runbooks/qa-cutover-checklist.md`。
- 目前已經有 `.github/workflows/qa.yml` 在 Python 3.13 上自動跑 `make lint`，以及 unit / contract / e2e / load import 驗證。
- 目前也已補上 `tests/unit/account/`、`tests/unit/search/`、`tests/unit/tradingagents/`，覆蓋 dashboard 組裝、search normalization、TradingAgents submit / poll 主流程。

## 3. 當前缺口

測試組尚未完成的交付：

- load 測試的實際壓測結果與基線留痕
- 灰度切流與回滾 runbook 的實地演練記錄

## 4. 後續開發順序

1. 執行 load tests 並留存結果
2. 演練灰度與回滾驗收模板

## 5. 已補文件與待執行項

```text
tests/load/locustfile.py
tests/load/scenarios/auth_read.py
tests/load/scenarios/dashboard_read.py
tests/load/scenarios/notification_read.py
tests/load/scenarios/trade_action.py
tests/load/scenarios/tradingagents_submit.py
ops/runbooks/qa-cutover-checklist.md
```

待執行：

- 以 staging fixture 跑一次 locust baseline，留存吞吐、錯誤率、P95 延遲。
- 依 `ops/runbooks/qa-cutover-checklist.md` 至少做一次 canary / rollback 演練。

常用命令：

- `make lint`
- `make test-qa`
- `make test-unit`
- `make qa-ci`
- `make test-load-import`
- `make load-help`
- `RELEASE_SHA=... QA_OWNER=... BACKEND_OWNER=... make load-report-init`
- `LOAD_TEST_HOST=... LOAD_TEST_ACCESS_TOKEN=... LOAD_TEST_REFRESH_TOKEN=... LOAD_TEST_TRADE_ID=... LOAD_TEST_TRADE_TOKEN=... make load-baseline`
- `RELEASE_SHA=... QA_OWNER=... BACKEND_OWNER=... ON_CALL_REVIEWER=... make cutover-report-init`
- `RELEASE_SHA=... OPENAPI_BASELINE_DIR=... make cutover-openapi-diff`

`make load-baseline` 會把報告輸出到 `ops/reports/load/<UTC timestamp>/baseline*`，方便直接附到 release record 或 cutover ticket。
`make load-report-init` 會在相同目錄預先建立 `baseline-summary.md`，`make cutover-report-init` 會建立 cutover rehearsal record 與對應的 `screenshots/`、`logs/` 目錄，而 `make cutover-openapi-diff` 會把 public/admin manifest 與 diff 摘要落到同一個 cutover report bundle 裡。

## 6. 目標接口與場景

### 6.1 Test Helpers

| 文件 | 類 / 函數 | 目標方法 |
|---|---|---|
| `tests/helpers/app_client.py` | `PublicApiClient` | `get()`, `post()`, `put()`, `delete()`, `auth_as_user()` |
| `tests/helpers/app_client.py` | `AdminApiClient` | `get()`, `post()`, `put()`, `delete()`, `auth_as_admin()` |
| `tests/helpers/factories.py` | `UserFactory` | `create_user()`, `create_session()` |
| `tests/helpers/factories.py` | `WatchlistFactory` | `create_watchlist_item()` |
| `tests/helpers/factories.py` | `PortfolioFactory` | `create_portfolio_position()` |
| `tests/helpers/factories.py` | `NotificationFactory` | `create_notification_with_receipt()` |
| `tests/helpers/event_assertions.py` | `assert_outbox_event()` | 驗證 outbox 有指定事件 |
| `tests/helpers/event_assertions.py` | `assert_kafka_event()` | 驗證 Kafka 消息 |
| `tests/contract/test_public_api_openapi.py` | `test_public_api_openapi_snapshot()` | 比對 OpenAPI snapshot |
| `tests/contract/test_admin_api_openapi.py` | `test_admin_api_openapi_snapshot()` | 比對 admin OpenAPI snapshot |

### 6.2 必測 e2e 場景

`test_auth_flow.py`：已落地，覆蓋 send-code、verify、logout、refresh

`test_subscription_flow.py`：已落地，覆蓋 account dashboard、watchlist create/update/delete、portfolio create/update/delete、start-subscription

`test_notification_flow.py`：已落地，覆蓋 notification list、push device register/disable/test、read-all、mark read、ack

`test_trade_flow.py`：已落地，覆蓋 public trade info、app trade info、confirm / ignore / adjust

`test_scanner_flow.py`：已落地，覆蓋 desktop signal ingest、payload normalization、scanner signal accepted response

`test_tradingagents_flow.py`：已落地，覆蓋 submit accepted、webhook terminal、admin analyses/stats、polling fallback

### 6.3 Load 測試要求

`tests/load/locustfile.py` 至少包含：

- `AuthReadUser`
- `DashboardReadUser`
- `NotificationReaderUser`
- `TradeActionUser`
- `TradingAgentsSubmitUser`

每個 user class 都必須有：

- 初始化 token
- 固定 scenario 權重
- request failure 統計

### 6.4 灰度驗收模板

`ops/runbooks/qa-cutover-checklist.md` 必須包含：

- 部署前檢查
- migration 檢查
- OpenAPI diff 檢查
- shadow read 檢查
- 雙寫比對檢查
- 回滾步驟
- 切流後 30 分鐘 / 2 小時 / 24 小時監控項

## 7. 驗收標準

測試組完成的判準：

- OpenAPI contract 可自動比對
- 公共 test helpers 可被 e2e / integration 共用
- 主要業務 e2e 全覆蓋
- 至少有一套 auth、dashboard、notifications、trade、TradingAgents 的 load scenario
- 有正式灰度驗收 checklist

## 8. 不要做的事情

- 不要只測 happy path
- 不要只寫單元測試而沒有 integration / e2e
- 不要讓壓測直接打生產環境
- 不要讓 contract 測試依賴手工比對