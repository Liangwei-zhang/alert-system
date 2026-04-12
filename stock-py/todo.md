
> Superseded by `docs/POST_MIGRATION_V2_PLAN.md`.
> This file is kept as an archived draft and is no longer the implementation-grade roadmap.


I'll first explore both repositories to understand the current state of the project, then provide a comprehensive design document.我已經深入研讀了你的 `stock-py` 項目全貌。以下是基於代碼倉庫實際狀態的完整設計文檔，重點針對你目前的三大瓶頸：**桌面端算法產出**、**退出策略**、以及 **300 萬日活的全鏈路承載能力**。

---

# stock-py 後期開發計劃 — 全面設計文檔

## 一、項目現狀審計

### 已完成（300+ 輪迭代成果）

| 層面 | 狀態 |
|---|---|
| Public API 主鏈路 | ✅ auth / account / watchlist / portfolio / search / notifications / trades / signal_ingest |
| Admin API | ✅ 40+ route，users / audit / acceptance / operators / distribution / tasks center / runtime / backtests / scanner / analytics |
| Workers | ✅ 13 個獨立 worker，覆蓋 scanner / market_data / backtest / event_pipeline / notification / push / email / receipt_escalation / retention / tradingagents_bridge / analytics_sink / cold_storage |
| 事件鏈路 | ✅ Durable outbox → Redis Streams / Kafka broker → dispatcher → subscriber 鏈路 |
| 數據平面 | ✅ PostgreSQL + PgBouncer + Redis + Kafka + ClickHouse + MinIO scaffold |
| 部署運維 | ✅ Docker Compose + Nginx + K8s baseline + load/cutover 工具鏈 |
| 三端 UI | ✅ Python 直出 HTML shell（/app, /platform, /admin） |
| QA 體系 | ✅ unit + contract + e2e + load + integration |

### 核心瓶頸定位

通過分析 `domains/signals/live_strategy_engine.py`，我看到了問題所在：

```python
# 當前策略選擇 — 過於簡單的靜態閾值
if dislocation >= 0.03:
    strategy = "mean_reversion"
elif momentum >= 0.65:
    strategy = "trend_continuation"
elif volatility >= 0.75:
    strategy = "volatility_breakout"
else:
    strategy = "range_rotation"
```

**瓶頸 1**：`LiveStrategyEngine.select_strategy()` 只有 4 個硬編碼閾值分支，沒有自適應能力、沒有多因子組合、沒有回測反饋迴路。

**瓶頸 2**：`score_candidate()` 的評分完全是固定權重線性累加（base 32 + bias 8 + confidence 25% + probability 30 + risk_reward 15 + volume 8 + trend 8 + reversal 6 + quality 15 - penalties），沒有根據歷史勝率動態調整。

**瓶頸 3**：退出策略（stop_loss / take_profit_1,2,3）完全由桌面端外部傳入，服務端沒有任何自主計算能力——只是存儲和轉發。

**瓶頸 4**：300 萬日活需要的水平擴展、分區推送、連線管理等工程化能力尚未落地。

---

## 二、核心算法生產車間重構（最高優先級）

### Phase 1：多因子策略引擎（2-3 週）

**目標**：將 `LiveStrategyEngine` 從 4 個 if-else 升級為可插拔的多因子策略框架。

#### 2.1 策略註冊框架

```
domains/signals/
├── strategies/
│   ├── __init__.py
│   ├── base.py                    # StrategyProtocol 抽象基類
│   ├── registry.py                # 策略註冊表 + 動態載入
│   ├── mean_reversion.py          # 均值回歸策略
│   ├── trend_continuation.py      # 趨勢延續策略
│   ├── volatility_breakout.py     # 波動率突破策略
│   ├── range_rotation.py          # 區間輪動策略
│   ├── momentum_divergence.py     # 動量背離策略（新增）
│   ├── volume_climax.py           # 量能高潮策略（新增）
│   ├── multi_timeframe.py         # 多時間框架共振策略（新增）
│   └── composite.py               # 組合策略投票器
├── scoring/
│   ├── __init__.py
│   ├── adaptive_scorer.py         # 自適應評分引擎
│   ├── factor_weights.py          # 因子權重管理
│   └── calibration.py             # 基於回測結果的校準器
├── exit_engine/
│   ├── __init__.py
│   ├── base.py                    # ExitStrategyProtocol
│   ├── atr_based.py               # ATR 動態止損/止盈
│   ├── trailing_stop.py           # 追蹤止損
│   ├── time_decay.py              # 時間衰減退出
│   ├── volatility_adjusted.py     # 波動率自適應退出
│   └── composite_exit.py          # 多條件組合退出
├── market_regime/
│   ├── __init__.py
│   ├── detector.py                # 市場狀態偵測器
│   ├── hmm_regime.py              # 隱馬爾可夫鏈狀態識別
│   ├── volatility_regime.py       # 波動率區間判定
│   └── trend_regime.py            # 趨勢/震盪判定
└── live_strategy_engine.py        # 重構後的協調者
```

#### 2.2 策略基類設計

```python
# domains/signals/strategies/base.py
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass

@dataclass(frozen=True)
class StrategyDecision:
    """策略決策結果"""
    strategy_name: str
    confidence: float          # 0.0-1.0，策略對自身判斷的信心
    signal_type: str | None    # buy / sell / None(不操作)
    entry_price: float | None
    stop_loss: float | None
    take_profit_targets: list[float]
    risk_reward_ratio: float | None
    reasons: list[str]
    metadata: dict[str, Any]

class BaseStrategy(ABC):
    """所有策略的抽象基類"""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def required_indicators(self) -> list[str]:
        """聲明本策略需要的指標，用於預計算"""
        ...

    @abstractmethod
    def evaluate(
        self,
        symbol: str,
        snapshot: dict[str, Any],
        historical: list[dict[str, Any]] | None = None,
        regime: str = "unknown",
    ) -> StrategyDecision | None:
        """
        評估是否產生信號。
        返回 None 表示本策略在當前條件下不產生信號。
        """
        ...

    @abstractmethod
    def applicable_regimes(self) -> set[str]:
        """本策略適用的市場狀態"""
        ...

    def weight_in_regime(self, regime: str) -> float:
        """本策略在指定市場狀態下的投票權重，預設 1.0"""
        return 1.0 if regime in self.applicable_regimes() else 0.3
```

#### 2.3 組合策略投票器

```python
# domains/signals/strategies/composite.py
class CompositeStrategyVoter:
    """
    多策略投票機制：
    1. 遍歷所有已註冊策略
    2. 過濾掉不適用當前市場狀態的策略
    3. 根據歷史勝率加權投票
    4. 只有超過閾值的信號才被採納
    """

    def __init__(
        self,
        strategies: list[BaseStrategy],
        min_agreement_ratio: float = 0.6,    # 至少 60% 策略同意
        min_confidence: float = 0.5,          # 最低加權信心
    ):
        self.strategies = strategies
        self.min_agreement_ratio = min_agreement_ratio
        self.min_confidence = min_confidence

    def vote(
        self,
        symbol: str,
        snapshot: dict[str, Any],
        historical: list[dict[str, Any]] | None,
        regime: str,
        historical_accuracy: dict[str, float] | None = None,
    ) -> StrategyDecision | None:
        """
        加權投票流程：
        1. 收集每個策略的決策
        2. 按歷史準確率加權
        3. 多數決定信號方向
        4. 加權合成信心分數
        5. 取最保守的止損、最激進的第一止盈
        """
        ...
```

### Phase 2：退出策略引擎（2 週）

**核心問題**：當前 stop_loss / take_profit 完全由桌面端外部傳入。服務端必須具備自主計算能力。

#### 2.4 ATR 自適應退出

```python
# domains/signals/exit_engine/atr_based.py
class ATRExitEngine:
    """
    基於 ATR（平均真實範圍）的動態退出計算

    入場後動態調整：
    - stop_loss = entry_price - atr_multiplier × ATR（做多）
    - take_profit_1 = entry_price + 1.5 × ATR
    - take_profit_2 = entry_price + 2.5 × ATR
    - take_profit_3 = entry_price + 4.0 × ATR

    關鍵改進：
    - ATR 值由服務端從 OHLCV 計算，不依賴桌面端傳入
    - multiplier 根據市場狀態自適應（volatile 用更大 multiplier）
    - 支持分批止盈：TP1 出 40%，TP2 出 30%，TP3 出 30%
    """

    def compute_exit_levels(
        self,
        entry_price: float,
        signal_type: str,         # buy / sell
        atr_value: float,
        regime: str,
        volatility_rank: float,   # 0-1，當前波動率在歷史中的百分位
    ) -> ExitLevels:
        # 根據市場狀態自適應乘數
        base_multiplier = self._regime_multiplier(regime)
        vol_adjustment = 1.0 + (volatility_rank - 0.5) * 0.5

        sl_distance = atr_value * base_multiplier * vol_adjustment
        ...
```

#### 2.5 追蹤止損

```python
# domains/signals/exit_engine/trailing_stop.py
class TrailingStopEngine:
    """
    持倉期間的動態追蹤止損

    三階段模型：
    1. 初始階段：固定止損（ATR-based）
    2. 保本階段：價格突破 TP1 後，止損移到入場價 + spread
    3. 追蹤階段：價格突破 TP2 後，止損跟隨最高價回撤 1.5×ATR

    觸發退出的條件：
    - 價格觸及止損 → 全部出場
    - 價格觸及 TP1 → 出場 40%
    - 價格觸及 TP2 → 再出場 30%，止損提升
    - 價格觸及 TP3 → 剩餘全部出場
    - 持倉超過 max_holding_bars → 時間衰減退出
    """
```

#### 2.6 時間衰減退出

```python
# domains/signals/exit_engine/time_decay.py
class TimeDecayExitEngine:
    """
    避免信號「釘子戶」：
    - 入場後 N 根 K 線（根據 strategy_window 計算）內未達 TP1
    - 逐步收緊止盈目標
    - 超過 max_holding_period 強制市價退出

    市場狀態自適應：
    - trend 環境：max_holding = 20 bars
    - range 環境：max_holding = 8 bars
    - volatile 環境：max_holding = 5 bars
    """
```

### Phase 3：Market Regime 偵測升級（1-2 週）

**當前問題**：`_infer_market_regime()` 只用 volatility_score 和 trend_strength 兩個靜態閾值。

#### 2.7 多維度 Regime 偵測器

```python
# domains/signals/market_regime/detector.py
class MarketRegimeDetector:
    """
    多維度市場狀態識別：

    輸入維度：
    1. 波動率維度：ATR%、Bollinger bandwidth、VIX 類比
    2. 趨勢維度：ADX、均線排列、線性回歸斜率
    3. 成交量維度：量比、OBV 斜率、量能分布
    4. 市場寬度：漲跌家數比（若為指數型標的）

    輸出狀態：
    - trending_up：強趨勢上漲
    - trending_down：強趨勢下跌
    - ranging：震盪區間
    - volatile：高波動
    - breakout：突破初期
    - exhaustion：趨勢衰竭

    每種狀態對應不同的策略權重和退出參數。
    """

    def detect(
        self,
        ohlcv_bars: list[dict[str, Any]],
        lookback: int = 50,
    ) -> RegimeResult:
        ...
```

### Phase 4：回測反饋迴路（2 週）

#### 2.8 策略效能追蹤

```python
# domains/signals/scoring/calibration.py
class StrategyCalibrator:
    """
    基於歷史交易結果校準策略權重和閾值：

    數據來源：
    - trades 表中的已完成交易
    - signals 表中的歷史信號
    - backtest runs 的結果

    校準流程（每日 scheduler 觸發）：
    1. 統計每個策略在不同 regime 下的勝率、盈虧比
    2. 更新 CompositeStrategyVoter 的投票權重
    3. 更新 AdaptiveScorer 的因子權重
    4. 記錄校準結果到 analytics

    約束：
    - 單次校準的權重調整幅度 ≤ 10%
    - 最低權重 ≥ 0.1（不完全淘汰策略）
    - 校準結果需回測驗證後才生效
    """
```

---

## 三、300 萬日活全鏈路承載設計

### 容量規劃

| 指標 | 計算 | 數值 |
|---|---|---|
| 日活用戶 | 目標 | 3,000,000 |
| 峰值同時在線 | 日活 × 15% | 450,000 |
| API QPS（讀） | 峰值在線 × 0.5 req/s | 225,000 |
| API QPS（寫） | 峰值在線 × 0.05 req/s | 22,500 |
| WebPush 推送/分鐘 | 信號 × 受眾 × 通道 | ~500,000 |
| 信號產生/小時 | scanner 覆蓋 × 策略 | ~200-500 |
| Kafka 事件 TPS | 寫入 + fanout | ~10,000 |
| PostgreSQL 連線 | API pods × pool | ~2,000 (via PgBouncer) |

### 3.1 訂閱端（Subscriber）— 300 萬用戶承載

#### 3.1.1 讀路徑優化

```
用戶請求 → Nginx/CDN → API Gateway
  ├── 靜態資源 → CDN 邊緣快取（HTML shell + JS/CSS）
  ├── 用戶數據 → Redis L1 快取 → PostgreSQL
  │   ├── session/profile: Redis TTL 30min
  │   ├── watchlist: Redis TTL 5min + invalidation
  │   ├── portfolio: Redis TTL 1min
  │   └── notifications: Redis Sorted Set per user
  └── 行情數據 → Redis pub/sub + client-side WebSocket
```

**關鍵改動**：

```python
# infra/cache/tiered_cache.py
class TieredCacheManager:
    """
    三級快取架構：
    L0: 進程內 LRU（最近 1000 個熱用戶的 session）
    L1: Redis（所有活躍用戶數據）
    L2: PostgreSQL（持久化）

    invalidation 策略：
    - write-through: 寫入時同步更新 L1
    - event-driven: outbox 事件觸發跨 pod 的 L0 失效
    """
```

#### 3.1.2 推送通道分層

```python
# domains/notifications/fanout_strategy.py
class FanoutStrategy:
    """
    300 萬用戶的信號推送不能串行：

    分層策略：
    1. VIP 用戶（付費訂閱）: 直接推送，延遲 < 3s
    2. 標準用戶: 批量推送，延遲 < 30s
    3. 免費用戶: 延遲推送，延遲 < 5min

    分區推送：
    - 按 user_id % partition_count 分到不同 Kafka partition
    - 每個 partition 對應一個 push_dispatch worker instance
    - 預計 20 個 partition 可承載 500K 推送/分鐘

    背壓控制：
    - WebPush provider 限速 → 本地 token bucket
    - Email provider 限速 → batch + rate limiter
    - Telegram 限速 → 30 msg/s per bot → 多 bot 分流
    """
```

#### 3.1.3 WebSocket 連線管理

```python
# infra/ws/connection_manager.py
class ScalableConnectionManager:
    """
    45 萬同時在線的 WebSocket 管理：

    單 pod 上限：~5,000 連線（受 file descriptor 限制）
    需要 pod 數量：450,000 / 5,000 = 90 pods

    跨 pod 廣播方案：
    - Redis pub/sub 作為 message bus
    - 每個 pod subscribe 全局 channel
    - 行情更新廣播到所有 connected clients

    降級策略：
    - WebSocket 不可用 → fallback 到 polling（30s 間隔）
    - Redis pub/sub 斷開 → 本地 buffer + reconnect
    """
```

### 3.2 桌面端（Platform）— 算法 + 監控承載

#### 3.2.1 Scanner Worker 水平擴展

```python
# apps/workers/scanner/distributed_scanner.py
class DistributedScannerCoordinator:
    """
    當前 scanner 是單節點循環掃描，300 萬日活下需要：
    - 監控標的數量：~5,000-10,000 symbols
    - 掃描頻率：每 5 分鐘全量
    - 單次掃描計算量：5,000 × 6 策略 × 指標計算

    水平分佈方案：
    1. symbol 按 hash 分到 N 個 scanner worker
    2. 每個 worker 負責 ~500-1000 symbols
    3. Redis 分佈式鎖避免重複掃描
    4. 結果寫入 signals 表 + outbox
    5. coordinator scheduler 負責分配和監控

    分桶（bucket）策略（已有 ScannerBucketItem schema）：
    - bucket 0: watchlist 命中的 symbols（最高優先）
    - bucket 1: 高流動性 symbols（每 1 分鐘）
    - bucket 2: 中流動性 symbols（每 5 分鐘）
    - bucket 3: 低流動性 symbols（每 15 分鐘）
    """
```

#### 3.2.2 行情數據管道

```python
# apps/workers/market_data/realtime_pipeline.py
class RealtimeMarketDataPipeline:
    """
    當前 market_data worker 是批量導入模式。
    300 萬日活需要近實時行情：

    數據源分層：
    1. Yahoo Finance: 免費，15 分鐘延遲，適合基礎報價
    2. Polygon.io / Alpha Vantage: 付費，準實時
    3. 交易所直連 WebSocket: 最低延遲

    數據流：
    data_source → Kafka topic (market.ohlcv) → 
      ├── Redis (最新報價快取)
      ├── PostgreSQL (OHLCV 歷史)
      ├── ClickHouse (tick 級別分析)
      └── WebSocket broadcast (行情推送)
    """
```

### 3.3 管理端（Admin）— 運維承載

#### 3.3.1 Runtime 監控強化

```python
# apps/admin_api/routers/runtime_monitoring.py 擴展
"""
300 萬日活的運維面板需要：

1. 實時指標（已有基礎）
   - API latency P50/P95/P99（需升級為滑動窗口）
   - worker 處理延遲分佈
   - 推送成功率/失敗率

2. 容量預警（需新建）
   - PostgreSQL 連線池使用率 > 80% → alert
   - Redis 記憶體 > 85% → alert（已有 threshold）
   - Kafka consumer lag > 200 → alert（已有 threshold）
   - push dispatch queue depth > 10,000 → alert

3. 業務指標（需新建）
   - 每日新增/流失用戶
   - 信號準確率趨勢（需回測反饋迴路）
   - 訂閱轉換率
   - 推送觸達率
"""
```

### 3.4 數據庫分層架構

```
┌─────────────────────────────────────────────────┐
│                    應用層                         │
├─────────────────────────────────────────────────┤
│                  PgBouncer                       │
│          (transaction pooling, 2000 連線)         │
├─────────────────────────────────────────────────┤
│  PostgreSQL Primary          PostgreSQL Replica   │
│  (寫入 + 強一致讀)           (讀取水平擴展)         │
│                                                   │
│  分區策略：                                        │
│  - signals: 按月 RANGE 分區                       │
│  - notifications: 按月 RANGE 分區                 │
│  - event_outbox: 按日 RANGE 分區 + TTL            │
│  - message_receipts_archive: 按月分區              │
│  - trades: 不分區（量級可控）                       │
│  - users/accounts: 不分區（量級可控）               │
├─────────────────────────────────────────────────┤
│  Redis Cluster (3 主 3 從)                        │
│  - session/token: slot 0-5460                    │
│  - cache/watchlist: slot 5461-10922              │
│  - streams/pubsub: slot 10923-16383              │
├─────────────────────────────────────────────────┤
│  Kafka (3 broker, ISR=2)                         │
│  - stock-py.events: 20 partitions                │
│  - market.ohlcv: 10 partitions                   │
│  - notifications.fanout: 20 partitions           │
├─────────────────────────────────────────────────┤
│  ClickHouse (analytics 寫入/查詢)                 │
│  - 已有 TTL: CLICKHOUSE_TABLE_TTL_DAYS=180       │
│  - 冷數據 → MinIO archive                        │
└─────────────────────────────────────────────────┘
```

---

## 四、開發路線圖

### 第一階段：突破算法瓶頸（4-6 週）— 上線的前置條件

| 週次 | 任務 | 交付物 |
|---|---|---|
| W1 | 策略基類 + 註冊框架 + 4 個現有策略抽取重構 | `domains/signals/strategies/*`，現有行為零回歸 |
| W2 | 退出策略引擎（ATR-based + trailing stop + time decay） | `domains/signals/exit_engine/*`，服務端自主計算 stop_loss / take_profit |
| W3 | Market Regime 偵測器升級（多維度輸入 + 6 種狀態） | `domains/signals/market_regime/detector.py` |
| W4 | 組合投票器 + 自適應評分 + 新增 3 個策略 | `strategies/composite.py`, `scoring/adaptive_scorer.py` |
| W5 | 回測反饋迴路 + 策略校準器 | `scoring/calibration.py`，scheduler 定時校準任務 |
| W6 | 集成測試 + 回測驗證 + 策略效能報告 | `tests/integration/signals/`，backtest worker 對接新引擎 |

**里程碑**：桌面端 scanner 從「4 個 if-else」升級為「6+ 策略投票 + 自適應退出 + 市場狀態感知」，信號品質可量化追蹤。

### 第二階段：300 萬日活工程化（4-6 週）

| 週次 | 任務 | 交付物 |
|---|---|---|
| W7 | 三級快取架構 + 讀路徑優化 | `infra/cache/tiered_cache.py` |
| W8 | 推送分層 fanout + Kafka partition 擴展 | `domains/notifications/fanout_strategy.py` |
| W9 | Scanner 水平分佈 + bucket 分級掃描 | `apps/workers/scanner/distributed_scanner.py` |
| W10 | PostgreSQL 分區 + read replica 路由 | Alembic migration + `infra/db/read_replica.py` |
| W11 | Redis Cluster 遷移 + WebSocket 管理 | `infra/ws/connection_manager.py` |
| W12 | 全鏈路壓測（Locust 升級到 300K 模擬） | `tests/load/` 升級，load baseline 報告 |

### 第三階段：產品化收尾（3-4 週）

| 週次 | 任務 | 交付物 |
|---|---|---|
| W13 | 三端 HTML UI 功能覆蓋（subscriber 端完整流程） | `/app` 完整 UX |
| W14 | Platform UI 功能覆蓋（策略監控面板 + 信號品質視圖） | `/platform` 研究台 |
| W15 | Admin UI 功能覆蓋（用戶管理 + 運營面板 + 告警） | `/admin` 運營台 |
| W16 | Staging 真實環境 rehearsal + cutover signoff | `ops/reports/` 真實 artifact |

---

## 五、退出策略的完整生命週期設計

這是目前項目最大的功能缺口之一。以下是端到端設計：

```
信號產生                持倉管理              退出執行
┌──────────┐         ┌───────────┐         ┌───────────┐
│ scanner  │──信號──→│ position  │──監控──→│ exit      │
│ + 策略   │         │ tracker   │         │ engine    │
│ 投票器   │         │           │         │           │
│          │         │ 記錄:     │         │ 檢查:     │
│ 產出:    │         │ - 入場價  │         │ - 止損    │
│ - entry  │         │ - 持倉量  │         │ - 止盈1/2/3│
│ - SL/TP  │         │ - 持倉K線 │         │ - 追蹤止損│
│ - regime │         │ - 最高價  │         │ - 時間衰減│
└──────────┘         │ - 當前PnL │         │ - 強制平倉│
                     └───────────┘         └───────────┘
                           │                      │
                           ▼                      ▼
                     ┌───────────┐         ┌───────────┐
                     │ outbox    │         │ trade     │
                     │ 事件發布  │         │ 確認/結算 │
                     │           │         │           │
                     │ position  │         │ exit      │
                     │ .updated  │         │ .triggered│
                     └───────────┘         └───────────┘
                           │                      │
                           ▼                      ▼
                     推送到訂閱端          記錄到 analytics
```

```python
# domains/signals/exit_engine/composite_exit.py
class CompositeExitEngine:
    """
    整合所有退出條件的主引擎：

    每次 scanner 循環（或行情更新時）調用 evaluate_exits()：
    1. 取出所有活躍持倉
    2. 對每個持倉執行退出條件檢查
    3. 觸發退出 → 發布 exit.triggered 事件

    退出優先級（由高到低）：
    1. 硬止損觸發 → 立即全部退出
    2. TP3 觸發 → 剩餘全部退出
    3. TP2 觸發 → 出場 30%，提升止損到 TP1
    4. TP1 觸發 → 出場 40%，止損移到入場價
    5. 追蹤止損觸發 → 全部退出
    6. 時間衰減 → 市價退出
    7. 市場狀態突變（regime 從 trend 切到 volatile）→ 收緊止損
    """

    def evaluate_exits(
        self,
        positions: list[ActivePosition],
        current_prices: dict[str, float],
        current_regimes: dict[str, str],
    ) -> list[ExitDecision]:
        ...
```

---

## 六、關鍵技術決策建議

| 決策點 | 建議 | 理由 |
|---|---|---|
| 行情數據源 | 起步用 Yahoo（免費）+ Polygon（付費），後期直連交易所 | 控制初期成本，同時預留擴展 |
| ML 模型引入 | 第一階段不引入 ML，用規則 + 統計；第二階段考慮 LightGBM 做信號評分 | 規則可解釋、可調試，ML 黑盒不適合早期產品 |
| 前端框架 | 保持純 HTML shell + vanilla JS，不引入 React/Vue | Python 直出 HTML 是正確選擇，300 萬用戶的前端走 CDN，服務端只管 API |
| K8s vs Compose | 第一階段繼續 Compose + VM，第二階段切 K8s | 你已有 K8s baseline，但先把業務做對再做擴展 |
| 付費訂閱接入 | 第二階段末期接 Stripe/Paddle | 不影響核心架構，是獨立域 |

---

## 七、風險與緩解

| 風險 | 影響 | 緩解措施 |
|---|---|---|
| 新策略引擎回歸 | 現有信號品質下降 | 新舊引擎並行運行 2 週，shadow mode 對比產出 |
| 退出引擎複雜度 | bug 導致錯誤平倉 | 退出決策先發通知、人工確認模式，逐步自動化 |
| 300 萬壓測缺 staging | 未知容量瓶頸 | 先用 Locust 壓 10 萬級，再逐步放量 |
| 單人開發效率 | 16 週計劃可能延期 | 優先級嚴格排序，算法瓶頸 > 擴展性 > UI |
| 行情數據成本 | Yahoo 限速、Polygon 付費 | 先用免費源 + 本地快取，用戶付費後升級數據源 |

---

## 總結

你的項目基建已經非常紮實（300+ 輪迭代不是白費的）。**三個核心突破點**按優先級排序：

1. **最優先（直接決定能否上線）**：重構 `LiveStrategyEngine`，從 4 個 if-else 升級為多策略投票 + 自適應退出 + 市場狀態感知。這是桌面端算法車間的核心。

2. **次優先（決定信號品質）**：建立服務端自主的退出策略引擎，不再完全依賴桌面端傳入 stop_loss / take_profit。

3. **第三優先（決定能否承載 300 萬）**：推送 fanout 分層 + scanner 水平分佈 + 讀路徑三級快取。

建議**先集中 6 週攻克算法和退出策略**，讓產品核心價值（信號品質）有實質提升，然後再做 300 萬日活的工程化。