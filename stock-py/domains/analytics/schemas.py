from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OverviewMetricsResponse(BaseModel):
    window_hours: int
    generated_signals: int = 0
    scanner_decisions: int = 0
    notification_requests: int = 0
    delivered_notifications: int = 0
    acknowledged_notifications: int = 0
    trade_actions: int = 0
    subscriptions_started: int = 0
    tradingagents_terminals: int = 0
    latest_event_at: datetime | None = None


class DistributionChannelMetric(BaseModel):
    channel: str
    requested: int = 0
    delivered: int = 0


class DistributionMetricsResponse(BaseModel):
    window_hours: int
    requested_total: int = 0
    delivered_total: int = 0
    acknowledged_total: int = 0
    pending_acknowledgements: int = 0
    delivery_rate: float = 0.0
    acknowledgement_rate: float = 0.0
    channels: list[DistributionChannelMetric] = Field(default_factory=list)


class StrategyHealthItem(BaseModel):
    strategy_name: str
    rank: int
    score: float
    degradation: float
    symbols_covered: int
    signals_generated: int = 0
    timeframe: str = "1d"
    stable: bool = True
    top_symbols: list[dict] = Field(default_factory=list)
    as_of_date: datetime | None = None


class StrategyHealthResponse(BaseModel):
    window_hours: int
    strategies: list[StrategyHealthItem] = Field(default_factory=list)
    refreshed_at: datetime | None = None


class TradingAgentsMetricsResponse(BaseModel):
    window_hours: int
    requested_total: int = 0
    terminal_total: int = 0
    completed_total: int = 0
    failed_total: int = 0
    open_total: int = 0
    success_rate: float = 0.0
    avg_latency_seconds: float | None = None
    by_status: dict[str, int] = Field(default_factory=dict)
    by_final_action: dict[str, int] = Field(default_factory=dict)


class AnalyticsBucketCountResponse(BaseModel):
    key: str
    count: int


class SignalTradeAlignmentItem(BaseModel):
    symbol: str
    signals_generated: int = 0
    trade_actions: int = 0
    executed_trades: int = 0
    execution_rate: float = 0.0


class ComparableFieldSetResponse(BaseModel):
    category: str
    fields: list[str] = Field(default_factory=list)
    note: str | None = None


class SignalResultMetricsResponse(BaseModel):
    window_hours: int
    generated_after: datetime
    total_signals: int = 0
    total_trade_actions: int = 0
    confirmed_trades: int = 0
    adjusted_trades: int = 0
    ignored_trades: int = 0
    expired_trades: int = 0
    pending_trades: int = 0
    trade_action_rate: float = 0.0
    executed_trade_rate: float = 0.0
    unique_signal_symbols: int = 0
    unique_trade_symbols: int = 0
    overlapping_symbols: int = 0
    signal_strategies: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    market_regimes: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    trade_statuses: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    symbol_alignment: list[SignalTradeAlignmentItem] = Field(default_factory=list)
    comparable_field_sets: list[ComparableFieldSetResponse] = Field(default_factory=list)


class ExitQualityMetricsResponse(BaseModel):
    window_hours: int
    generated_after: datetime
    total_signals: int = 0
    exits_available: int = 0
    calibrated_exit_count: int = 0
    client_exit_count: int = 0
    avg_risk_reward_ratio: float = 0.0
    avg_atr_multiplier: float = 0.0
    avg_stop_distance_pct: float = 0.0
    avg_tp1_distance_pct: float = 0.0
    exit_sources: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    atr_multiplier_sources: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    market_regimes: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
    top_symbols: list[AnalyticsBucketCountResponse] = Field(default_factory=list)
