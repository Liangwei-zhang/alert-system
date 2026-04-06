# 通知組執行手冊

> 狀態（2026-04-04）：notifications / trades domain 與通知 worker 已落地；目前已有 `tests/e2e/test_notification_flow.py`、`tests/e2e/test_trade_flow.py`、`tests/integration/notifications/test_notifications_router.py` 與 `tests/integration/trades/test_trades_router.py` 作為 notifications/trade workflow baseline，更細的 integration 測試與後續補強項仍待補齊。

## 1. 目標

通知組負責把 `notifications + push/email + receipts + trade workflow` 做成一條獨立、可靠、可重試、可審計的分發鏈路。

## 2. 範圍邊界

通知組負責：

- notifications 查詢與命令 API
- push device 註冊 / 停用 / test
- notification orchestrator
- push dispatch worker
- email dispatch worker
- receipt escalation worker
- trade confirm / ignore / adjust 流程

通知組不負責：

- 使用者登入與 watchlist / portfolio CRUD
- scanner 策略生成
- TradingAgents submit / poll / webhook

## 3. 開發順序

1. notifications read / mark read / ack
2. push device register / disable / test
3. notification orchestrator
4. push/email dispatch workers
5. receipt escalation worker
6. trade workflow

## 4. 必建文件

```text
infra/db/models/notifications.py
infra/db/models/trades.py
domains/notifications/schemas.py
domains/notifications/repository.py
domains/notifications/query_service.py
domains/notifications/command_service.py
domains/notifications/push_service.py
domains/notifications/receipt_service.py
domains/trades/schemas.py
domains/trades/repository.py
domains/trades/link_security.py
domains/trades/html_renderer.py
domains/trades/service.py
apps/public_api/routers/notifications.py
apps/public_api/routers/trades.py
apps/workers/notification_orchestrator/worker.py
apps/workers/push_dispatch/worker.py
apps/workers/email_dispatch/worker.py
apps/workers/receipt_escalation/worker.py
tests/unit/notifications/
tests/unit/trades/
tests/integration/notifications/
tests/integration/trades/
```

## 5. 類與函數清單

### 5.1 Notifications

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
| `domains/notifications/receipt_service.py` | `ReceiptEscalationService` | `scan_and_escalate()`, `claim_manual_follow_up()`, `resolve_follow_up()` |

### 5.2 Trades

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/trades.py` | `TradeLogModel` | 對應 `trade_log` |
| `domains/trades/schemas.py` | `AdjustTradeRequest` | `actual_shares`, `actual_price` |
| `domains/trades/schemas.py` | `TradeInfoResponse` | `trade`, `is_expired`, `expires_at` |
| `domains/trades/repository.py` | `TradeRepository` | `get_by_id()`, `get_by_id_for_user()`, `update_status()`, `record_execution()`, `mark_ignored()` |
| `domains/trades/link_security.py` | `TradeLinkSigner` | `sign()`, `verify()`, `is_expired()` |
| `domains/trades/html_renderer.py` | `TradeHtmlRenderer` | `render_status_page()`, `render_confirm_page()` |
| `domains/trades/service.py` | `TradeService` | `get_public_info()`, `get_app_info()`, `confirm_trade()`, `ignore_trade()`, `adjust_trade()`, `acknowledge_trade_receipts()` |

## 6. Router 與 Worker 清單

| 文件 | 類 / 函數 | 路由或責任 |
|---|---|---|
| `apps/public_api/routers/notifications.py` | `list_notifications()` | `GET /v1/notifications` |
| `apps/public_api/routers/notifications.py` | `list_push_devices()` | `GET /v1/notifications/push-devices` |
| `apps/public_api/routers/notifications.py` | `register_push_device()` | `POST /v1/notifications/push-devices` |
| `apps/public_api/routers/notifications.py` | `disable_push_device()` | `DELETE /v1/notifications/push-devices/{device_id}` |
| `apps/public_api/routers/notifications.py` | `test_push_device()` | `POST /v1/notifications/push-devices/{device_id}/test` |
| `apps/public_api/routers/notifications.py` | `mark_all_read()` | `PUT /v1/notifications/read-all` |
| `apps/public_api/routers/notifications.py` | `mark_read()` | `PUT /v1/notifications/{id}/read` |
| `apps/public_api/routers/notifications.py` | `acknowledge()` | `PUT /v1/notifications/{id}/ack` |
| `apps/public_api/routers/trades.py` | `get_trade_info()` | `GET /v1/trades/{id}/info` |
| `apps/public_api/routers/trades.py` | `get_trade_app_info()` | `GET /v1/trades/{id}/app-info` |
| `apps/public_api/routers/trades.py` | `confirm_trade()` | `POST /v1/trades/{id}/confirm` |
| `apps/public_api/routers/trades.py` | `ignore_trade()` | `POST /v1/trades/{id}/ignore` |
| `apps/public_api/routers/trades.py` | `adjust_trade()` | `POST /v1/trades/{id}/adjust` |
| `apps/public_api/routers/trades.py` | `app_confirm_trade()` | `POST /v1/trades/{id}/app-confirm` |
| `apps/public_api/routers/trades.py` | `app_ignore_trade()` | `POST /v1/trades/{id}/app-ignore` |
| `apps/public_api/routers/trades.py` | `app_adjust_trade()` | `POST /v1/trades/{id}/app-adjust` |
| `apps/workers/notification_orchestrator/worker.py` | `NotificationOrchestratorWorker` | 消費 `signal.generated` 並寫 notification / outbox |
| `apps/workers/push_dispatch/worker.py` | `PushDispatchWorker` | 消費 `notification.requested` 並做 push 投遞 |
| `apps/workers/email_dispatch/worker.py` | `EmailDispatchWorker` | 消費 `notification.requested` 並做 email 投遞 |
| `apps/workers/receipt_escalation/worker.py` | `ReceiptEscalationWorker` | 掃逾期未 ack 的 receipt |

## 7. 事件輸入與輸出

通知組要消費：

- `signal.generated`
- `tradingagents.terminal`

通知組要輸出：

- `notification.requested`
- `notification.delivered`
- `notification.acknowledged`
- `trade.action.recorded`

## 8. 實作要求

### 8.1 Notification Query

`NotificationQueryService` 必須做到：

- 分頁查詢 notifications
- 關聯最新 receipt 狀態
- 不允許掃全表

### 8.2 Notification Command

`NotificationCommandService` 必須做到：

- 單條已讀
- 全部已讀
- 單條 ack
- 同步更新 receipt opened / acknowledged 狀態

### 8.3 Push Device

`PushSubscriptionService` 必須做到：

- upsert device
- disable device
- 發送 test push
- 對 invalid device 做失效處理

### 8.4 Orchestrator

`NotificationOrchestratorWorker` 必須做到：

- 將 signal 或 AI terminal event 映射成 notification payload
- bulk create notifications
- 寫 `message_outbox`
- 發 `notification.requested`

### 8.5 Dispatch Workers

兩個 dispatch worker 都必須做到：

- 每次投遞都記錄 `delivery_attempts`
- 成功後更新 `message_receipts`
- 失敗時區分 retryable / non-retryable
- 非法裝置 / 無效信箱要能標記並停止浪費重試

### 8.6 Trade Workflow

`TradeService` 必須做到：

- 驗證 signed link
- 驗證是否過期 / 是否已處理
- confirm / ignore / adjust 三條命令鏈路
- 成功後觸發 `trade.action.recorded`
- 成功後調用 portfolio projector 更新持倉

## 9. 驗收標準

通知組完成的判準：

- notifications 查詢、已讀、ack 跑通
- push device register / disable / test 跑通
- signal.generated 能轉成 notification.requested
- push/email 投遞具備重試與失敗記錄
- receipt escalation 能掃出 overdue receipt
- trade confirm / ignore / adjust 與 portfolio 回寫可追蹤

## 10. 不要做的事情

- 不要在 router 裡直接操作 `message_outbox`
- 不要在 dispatch worker 裡直接改 watchlist / portfolio
- 不要把 trade link 驗證散落在多個 router
- 不要讓 push worker 和 email worker 共用一套混亂的 provider fallback 邏輯