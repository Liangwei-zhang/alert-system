# 訊號組執行手冊

> 狀態（2026-04-04）：signals / backtest / market-data 代碼與對應 unit 測試已落地；本文中的 integration 測試目錄仍是 target-state 清單。

## 1. 目標

訊號組負責把現有桌面訊號、scanner、策略選擇、回測、OHLCV 品質治理搬到 Python，並做成可以水平擴展的 worker 鏈路。

## 2. 範圍邊界

訊號組負責：

- desktop signal ingest
- active symbols projection
- live strategy engine
- signal dedupe
- scanner shard worker
- backtest / ranking refresh
- OHLCV quality
- symbol metadata / 行情資料的掃描前置能力

訊號組不負責：

- push/email 發送
- 使用者 CRUD
- TradingAgents polling / webhook
- admin 大盤 read model

## 3. 開發順序

請按以下順序實作：

1. `ActiveSymbolsService`
2. `DesktopSignalService`
3. `LiveStrategyEngine`
4. `SignalDedupePolicy`
5. `ScannerWorker`
6. `BacktestService`
7. `OhlcvQualityService`
8. `MarketDataWorker`

## 4. 必建文件

```text
infra/db/models/signals.py
infra/db/models/market_data.py
domains/signals/schemas.py
domains/signals/repository.py
domains/signals/live_strategy_engine.py
domains/signals/desktop_signal_service.py
domains/signals/dedupe_policy.py
domains/signals/active_symbols_service.py
domains/analytics/backtest/repository.py
domains/analytics/backtest/service.py
domains/market_data/repository.py
domains/market_data/symbol_sync_service.py
domains/market_data/ohlcv_import_service.py
domains/market_data/quality_service.py
apps/public_api/routers/signal_ingest.py
apps/workers/scanner/worker.py
apps/workers/backtest/worker.py
apps/workers/market_data/worker.py
tests/unit/signals/
tests/unit/backtest/
tests/unit/market_data/
tests/integration/signals/
tests/integration/backtest/
tests/integration/market_data/
```

## 5. 類與函數清單

### 5.1 Signals

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/signals.py` | `SignalModel` | 對應 `signals` |
| `infra/db/models/signals.py` | `ScannerRunModel` | 對應 `scanner_runs` |
| `infra/db/models/signals.py` | `ScannerDecisionModel` | 對應 `scanner_decisions` |
| `domains/signals/schemas.py` | `DesktopSignalRequest` | `source`, `emitted_at`, `alert`, `analysis` |
| `domains/signals/schemas.py` | `SignalCandidate` | `symbol`, `type`, `score`, `price`, `reasons`, `analysis` |
| `domains/signals/schemas.py` | `ScannerBucketItem` | `bucket_id`, `symbol`, `priority` |
| `domains/signals/repository.py` | `SignalRepository` | `create_signal()`, `find_recent_duplicate()`, `list_recent_by_symbol()` |
| `domains/signals/repository.py` | `ScannerRunRepository` | `create_run()`, `finish_run()`, `create_decision()` |
| `domains/signals/live_strategy_engine.py` | `LiveStrategyEngine` | `select_strategy()`, `score_candidate()`, `build_signal_candidate()` |
| `domains/signals/desktop_signal_service.py` | `DesktopSignalService` | `ingest_desktop_signal()`, `route_signal()` |
| `domains/signals/dedupe_policy.py` | `SignalDedupePolicy` | `build_dedupe_key()`, `should_suppress()` |
| `domains/signals/active_symbols_service.py` | `ActiveSymbolsService` | `refresh_projection()`, `list_scan_buckets()`, `mark_symbol_dirty()` |

### 5.2 Backtest

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `domains/analytics/backtest/repository.py` | `BacktestRepository` | `save_run()`, `save_results()`, `save_rankings()`, `load_window_data()` |
| `domains/analytics/backtest/service.py` | `BacktestService` | `refresh_rankings()`, `run_backtest_window()`, `calculate_degradation()`, `build_strategy_evidence()` |

### 5.3 Market Data / Quality

| 文件 | 類 / 函數 | 必須實作的方法 |
|---|---|---|
| `infra/db/models/market_data.py` | `SymbolModel` | 對應 `symbols` |
| `infra/db/models/market_data.py` | `OhlcvModel` | 對應 `ohlcv` |
| `infra/db/models/market_data.py` | `OhlcvAnomalyModel` | 對應 `ohlcv_anomalies` |
| `domains/market_data/repository.py` | `SymbolRepository` | `bulk_upsert_symbols()`, `get_symbol()`, `list_active_symbols()` |
| `domains/market_data/repository.py` | `OhlcvRepository` | `bulk_upsert_bars()`, `quarantine_bad_rows()`, `get_recent_bars()` |
| `domains/market_data/symbol_sync_service.py` | `SymbolSyncService` | `sync_symbols()` |
| `domains/market_data/ohlcv_import_service.py` | `OhlcvImportService` | `import_batch()`, `normalize_bar()` |
| `domains/market_data/quality_service.py` | `OhlcvQualityService` | `validate_batch()`, `emit_quality_event()` |

## 6. Worker 與 Router 函數

| 文件 | 類 / 函數 | 路由或責任 |
|---|---|---|
| `apps/public_api/routers/signal_ingest.py` | `ingest_desktop_signal()` | `POST /v1/internal/signals/desktop` |
| `apps/workers/scanner/worker.py` | `ScannerWorker` | `run_forever()`, `run_once()`, `process_bucket()`, `process_symbol()` |
| `apps/workers/backtest/worker.py` | `BacktestWorker` | `run_forever()`, `refresh_rankings()` |
| `apps/workers/market_data/worker.py` | `MarketDataWorker` | `run_forever()`, `sync_symbols()`, `import_ohlcv()`, `run_quality_checks()` |

## 7. 事件輸入與輸出

訊號組要消費：

- `account.subscription.started`
- `watchlist.changed`
- `portfolio.changed`
- `marketdata.ohlcv.imported`

訊號組要輸出：

- `signal.generated`
- `marketdata.symbol.updated`
- `marketdata.ohlcv.imported`
- `ops.audit.logged`

## 8. 實作要求

### 8.1 Active Symbols

`ActiveSymbolsService` 必須做到：

- 從 watchlist / portfolio 變更事件更新投影，而不是每次掃描全量重算
- 支援 dirty symbol 局部刷新
- 能輸出 scanner shard bucket

### 8.2 Scanner

`ScannerWorker` 必須做到：

- 支援多 worker 依 bucket 並行掃描
- 每次掃描都寫 `scanner_runs`
- 每個 symbol 決策都寫 `scanner_decisions`
- 被抑制的 signal 也要記錄原因

### 8.3 Dedupe

`SignalDedupePolicy` 必須做到：

- 同 symbol + 同策略窗 + 同 regime + 同方向的 signal 在冷卻窗口內不重覆發送
- suppress 時保留決策記錄

### 8.4 Backtest

`BacktestService` 必須做到：

- 支援 rolling 30 / 90 / 180 / 365 天視窗
- 能刷新 strategy ranking
- 能輸出 degradation 與 evidence

### 8.5 OHLCV Quality

`OhlcvQualityService` 必須做到：

- 異常值隔離
- 缺 bar、重複 bar、時間倒退檢測
- 發品質事件供數據組和 admin 看板使用

## 9. 驗收標準

訊號組完成的判準：

- active symbols 不再依賴 request-time 臨時計算
- 15,000 symbols / 5 分鐘的掃描週期可完成
- 相同 signal 在冷卻窗口內不重覆大規模 fanout
- backtest 刷新能生成 ranking 與 evidence
- OHLCV 異常可被隔離與統計

## 10. 不要做的事情

- 不要在 scanner 內直接發 push 或 email
- 不要在 signal service 內直接更新 notifications 表
- 不要在 market-data worker 內寫 admin read model
- 不要讓 backtest job 直接跑在 public API request 裡