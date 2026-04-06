# Python 改造分工索引

> 狀態（2026-04-04）：本目錄中的文檔同時包含「已落地現況」與「未完成的 target-state 清單」。若列出的測試、部署或運維目錄在 repo 中不存在，應視為待補交付，不代表倉庫已包含該內容。

本目錄是 [resume.md](./resume.md) 的團隊拆分版本。

用途：

- 讓每個團隊只看與自己直接相關的實施文檔。
- 讓新人拿到某一份文檔後，可以直接按文件、類、函數名開工。
- 讓項目負責人能直接把文檔拆成任務系統中的 Epic / Story。

## 閱讀順序

1. 先讀 [resume.md](./resume.md)
2. 再讀本索引
3. 平台組先讀 [PLATFORM_TEAM_EXECUTION.md](./PLATFORM_TEAM_EXECUTION.md)
4. 其他團隊讀各自對應文檔

## 文檔清單

| 團隊 | 文檔 | 主要範圍 |
|---|---|---|
| 平台組 | [PLATFORM_TEAM_EXECUTION.md](./PLATFORM_TEAM_EXECUTION.md) | 倉庫骨架、共用 infra、CI/CD、K8s、observability、依賴注入 |
| 帳戶組 | [ACCOUNT_TEAM_EXECUTION.md](./ACCOUNT_TEAM_EXECUTION.md) | auth、account、subscription、watchlist、portfolio、search |
| 訊號組 | [SIGNAL_TEAM_EXECUTION.md](./SIGNAL_TEAM_EXECUTION.md) | signal ingest、active symbols、scanner、backtest、OHLCV quality |
| 通知組 | [NOTIFICATION_TEAM_EXECUTION.md](./NOTIFICATION_TEAM_EXECUTION.md) | notifications、push/email、receipts、trade workflow |
| AI 整合組 | [AI_INTEGRATION_TEAM_EXECUTION.md](./AI_INTEGRATION_TEAM_EXECUTION.md) | TradingAgents gateway、orchestrator、polling、webhook、admin AI 視圖 |
| 數據組 | [DATA_TEAM_EXECUTION.md](./DATA_TEAM_EXECUTION.md) | ClickHouse、數據下沉、冷存、分析 read model |
| 測試組 | [QA_TEAM_EXECUTION.md](./QA_TEAM_EXECUTION.md) | contract、integration、e2e、load、灰度驗收 |

## 共同規則

所有團隊都必須遵守：

- 不修改主技術棧。
- 不把業務邏輯寫進 router。
- 不讓 repository 調外部服務。
- 所有寫接口都要有 idempotency 設計。
- 所有跨域副作用都要走 outbox + event bus。
- 類名、函數名、文件名按 [resume.md](./resume.md) 第 23、24 章執行。

## 團隊依賴關係

| 先完成的團隊 | 後依賴團隊 | 依賴內容 |
|---|---|---|
| 平台組 | 全部 | 共用 infra、Settings、DB session、EventBus、CI/CD |
| 帳戶組 | 訊號組、通知組 | watchlist / portfolio / subscription 事件 |
| 訊號組 | 通知組、AI 整合組、數據組 | signal.generated、scanner 決策資料 |
| 通知組 | 數據組、測試組 | notification.requested / delivered / ack 鏈路 |
| AI 整合組 | 數據組、測試組 | tradingagents.requested / terminal 鏈路 |
| 數據組 | admin、測試組 | ClickHouse read model、報表、分析匯總 |

## 新人分配原則

若是新加入成員，請按以下原則分配：

- 平台組新人先做 `config`、`errors`、`context` 這類小型公共模塊。
- 帳戶組新人先做 `auth/send-code`、`watchlist create`。
- 通知組新人先做 `notifications mark read`、`push device register`。
- 訊號組新人不要直接負責 `scanner-worker` 主循環。
- AI 整合組新人不要單獨負責 `polling + webhook + admin` 全鏈路。

## 任務拆分建議

每份團隊文檔都包含：

- 範圍邊界
- 必建文件
- 類與函數清單
- 實作順序
- 驗收標準
- 與其他團隊的交接點

文檔不只是參考說明，而是交付標準。若實作與文檔不一致，需要先改文檔再改代碼。