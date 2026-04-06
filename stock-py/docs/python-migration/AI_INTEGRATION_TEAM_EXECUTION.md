# AI 整合組執行手冊

> 狀態（2026-04-04）：TradingAgents 的 gateway、orchestrator、webhook、worker、admin router 已落地；目前已有 `tests/e2e/test_tradingagents_flow.py` 與 `tests/integration/tradingagents/test_admin_tradingagents_router.py` 作為 app-level 與 admin/router baseline，更廣泛的 integration 清單仍待逐步補齊。

## 1. 目標

AI 整合組負責把 TradingAgents 在 stock Python 系統中的接入做成穩定的非同步下游整合，而不是把 TradingAgents 變成 fast path 同步依賴。

## 2. 範圍邊界

AI 整合組負責：

- TradingAgents gateway client
- request_id 規則
- accepted request 落庫
- terminal webhook 接收
- polling reconciliation worker
- admin AI read model 所需 API

AI 整合組不負責：

- TradingAgents 服務本身的 graph / agent 內部實現
- scanner 的策略邏輯
- 通知的 provider 發送細節

## 3. 開發順序

1. `TradingAgentsGateway`
2. `RequestIdBuilder`
3. `TradingAgentsRepository`
4. `TradingAgentsProjectionMapper`
5. `TradingAgentsOrchestrator`
6. `TradingAgentsWebhookService`
7. `TradingAgentsPollingWorker`
8. admin `list_analyses` / `reconcile_delayed`

## 4. 必建文件

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
tests/e2e/test_tradingagents_flow.py
```

## 5. 類與函數清單

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/tradingagents.py` | `TradingAgentsAnalysisRecordModel` | 對應 `tradingagents_analysis_records` |
| `infra/db/models/tradingagents.py` | `TradingAgentsSubmitFailureModel` | 對應 `tradingagents_submit_failures` |
| `domains/tradingagents/schemas.py` | `SubmitTradingAgentsRequest` | `request_id`, `ticker`, `analysis_date`, `selected_analysts`, `trigger_type`, `trigger_context` |
| `domains/tradingagents/schemas.py` | `TradingAgentsProjection` | `request_id`, `job_id`, `tradingagents_status`, `final_action`, `decision_summary`, `error_code`, `error_message`, `result_payload` |
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

## 6. 核心規則

### 6.1 submit 規則

- 只能 async submit，不能在 scanner request path 同步等待結果
- `request_id` 由 stock 生成
- `job_id` 由 TradingAgents 返回
- accepted 後才寫 `tradingagents_analysis_records`

### 6.2 webhook 規則

- 只接受 terminal 事件
- 必須驗證 bearer token
- 必須驗證 event header
- webhook 只做驗證、映射、快速落庫，不做重型業務運算

### 6.3 polling 規則

- 只輪詢 `queued` / `running` 記錄
- 遇到 terminal 狀態立即停止
- 超過 stock 端 timeout budget 時標記 delayed，而不是 failed

## 7. 事件輸入與輸出

AI 整合組要消費：

- `signal.generated`
- `manual.review.requested` 或未來對應 admin 手動分析事件

AI 整合組要輸出：

- `tradingagents.requested`
- `tradingagents.terminal`
- `ops.audit.logged`

## 8. 本地開發與驗證要求

AI 整合組本地至少要能驗證三件事：

1. submit 成功並寫入 accepted record
2. webhook 能把 terminal result 寫回 stock
3. polling 能在 webhook 缺失時補齊結果

如果沒有真實 provider key，允許使用 TradingAgents 的 mock execution mode 做端到端驗證。

## 9. 驗收標準

AI 整合組完成的判準：

- TradingAgents 故障不影響 scanner fast path
- webhook 和 poller 能共同收斂到同一 canonical record
- `succeeded`、`failed`、`canceled`、`delayed` 狀態區分清楚
- admin 可查看分析列表與 delayed records

## 10. 不要做的事情

- 不要把 TradingAgents graph 直接內嵌到 stock Python 服務內
- 不要在 webhook handler 裡做同步通知 fanout
- 不要讓 poller 重覆提交已 accepted 的 request
- 不要把 delayed 直接當作 failed