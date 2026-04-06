# 數據組執行手冊

> 狀態（2026-04-04）：analytics 鏈路已能在本地跑通，但目前是 JSONL + 本地 object storage facade；Kafka / 真 ClickHouse / 外部 S3-compatible storage 仍未落地。

## 1. 目標

數據組負責建立 300 萬 DAU 所需的分析數據平面，讓 admin 報表、策略分析、投遞統計、AI 審計不再壓主業務庫。

## 2. 當前已落地

目前已存在的核心文件：

```text
infra/analytics/clickhouse_client.py
domains/analytics/schemas.py
domains/analytics/repository.py
domains/analytics/overview_read_model_service.py
domains/analytics/distribution_read_model_service.py
domains/analytics/strategy_read_model_service.py
domains/analytics/tradingagents_read_model_service.py
domains/analytics/sinks/signal_sink.py
domains/analytics/sinks/notification_sink.py
domains/analytics/sinks/tradingagents_sink.py
domains/analytics/archive/export_service.py
apps/workers/analytics_sink/worker.py
apps/workers/cold_storage/worker.py
tests/unit/analytics/
tests/integration/analytics/
```

當前行為：

- `ClickHouseClient` 會把資料寫入 `object_storage_root/clickhouse/<table>/YYYY-MM.jsonl`，以按月分區方式支撐本地開發與測試，避免單文件持續增長。
- `AnalyticsSinkWorker` 目前透過注入的 `event_source` 批量處理事件，尚未直接接 Kafka consumer。
- `ArchiveExportService` 會輸出 gzip JSONL 與 manifest，透過 `ObjectStorageClient` 寫入本地存儲根目錄。
- 四個 read model service 目前都從 `AnalyticsRepository` 取資料，不直接打 OLTP 主庫。

## 3. 當前缺口

數據組尚未完成的 productionization 項：

- 真 ClickHouse backend 與 schema 管理
- Kafka / Redpanda consumer、DLQ、重試策略
- 外部 S3 / MinIO 物件存儲接入
- 壓測與容量驗證

## 4. 建議開發順序

1. 保留現有本地 facade，擴展 integration tests 到更多失敗 / 補償場景
2. 把 sink worker 換成 Kafka / Redpanda consumer
3. 把 `ClickHouseClient` 從 JSONL facade 換成真實 backend
4. 補齊 signal / notification / TradingAgents analytics sink 的運維指標與錯誤補償
5. 把 cold storage 接到外部 object storage

## 5. 目標接口與文件

| 文件 | 類 / 函數 | 當前狀態 |
|---|---|---|
| `infra/analytics/clickhouse_client.py` | `ClickHouseClient` | 已落地，本地 JSONL facade |
| `domains/analytics/schemas.py` | `OverviewMetricsResponse` 等 | 已落地 |
| `domains/analytics/repository.py` | `AnalyticsRepository` | 已落地 |
| `domains/analytics/overview_read_model_service.py` | `OverviewReadModelService` | 已落地 |
| `domains/analytics/distribution_read_model_service.py` | `DistributionReadModelService` | 已落地 |
| `domains/analytics/strategy_read_model_service.py` | `StrategyReadModelService` | 已落地 |
| `domains/analytics/tradingagents_read_model_service.py` | `TradingAgentsReadModelService` | 已落地 |
| `domains/analytics/sinks/signal_sink.py` | `SignalAnalyticsSink` | 已落地 |
| `domains/analytics/sinks/notification_sink.py` | `NotificationAnalyticsSink` | 已落地 |
| `domains/analytics/sinks/tradingagents_sink.py` | `TradingAgentsAnalyticsSink` | 已落地 |
| `domains/analytics/archive/export_service.py` | `ArchiveExportService` | 已落地，本地 object storage facade |
| `apps/workers/analytics_sink/worker.py` | `AnalyticsSinkWorker` | 已落地，Kafka 接入待補 |
| `apps/workers/cold_storage/worker.py` | `ColdStorageWorker` | 已落地 |
| `tests/unit/analytics/` | analytics unit tests | 已落地 |
| `tests/integration/analytics/` | analytics integration tests | 已落地，覆蓋 worker -> read model pipeline |

## 6. 事件主題與當前支持

目前 worker 已支持或預留這些事件主題：

- `account.subscription.started`
- `watchlist.changed`
- `portfolio.changed`
- `signal.generated`
- `scanner.decision.recorded`
- `strategy.rankings.refreshed`
- `notification.requested`
- `notification.delivered`
- `notification.acknowledged`
- `trade.action.recorded`
- `tradingagents.requested`
- `tradingagents.terminal`

## 7. 目標實作要求

### 7.1 Sink Worker

`AnalyticsSinkWorker` 的 target state：

- 從 Kafka / Redpanda 批量消費
- 依事件類型路由到各 sink class
- 失敗記錄 DLQ 或重試狀態

### 7.2 Read Model Service

四個 read model service 都必須做到：

- 只讀 analytics backend，不直接打 OLTP 主庫
- 輸出穩定的 admin 聚合結構
- 支援時間窗查詢

### 7.3 Archive

`ArchiveExportService` 的 target state：

- 將舊分區壓縮後輸出到 S3 / MinIO
- 保留 manifest
- 支援回查與重建

## 8. 驗收標準

數據組完成的判準：

- admin 大盤、distribution、strategy health、TradingAgents 指標都能在不壓主庫的情況下查詢
- analytics sink 可穩定消費事件流
- 冷資料可匯出且可回查

## 9. 不要做的事情

- 不要直接從 admin router 打 PostgreSQL 長查詢做報表
- 不要在 sink worker 裡實作業務規則
- 不要讓 ClickHouse 成為寫路徑事實源