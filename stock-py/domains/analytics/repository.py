from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from infra.analytics.clickhouse_client import ClickHouseClient


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalyticsRepository:
    def __init__(self, client: ClickHouseClient) -> None:
        self.client = client

    async def query_overview(self, window_hours: int = 24) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(hours=window_hours)
        signal_rows = await self.client.query_rows("signal_events", start_at=cutoff)
        scanner_rows = await self.client.query_rows("scanner_decision_events", start_at=cutoff)
        notification_rows = await self.client.query_rows("notification_events", start_at=cutoff)
        receipt_rows = await self.client.query_rows("receipt_events", start_at=cutoff)
        trade_rows = await self.client.query_rows("trade_events", start_at=cutoff)
        subscription_rows = await self.client.query_rows("subscription_events", start_at=cutoff)
        ta_rows = await self.client.query_rows(
            "tradingagents_events",
            start_at=cutoff,
            filters={"event_type": "terminal"},
        )
        latest = self._latest_timestamp(
            signal_rows,
            scanner_rows,
            notification_rows,
            receipt_rows,
            trade_rows,
            subscription_rows,
            ta_rows,
        )
        return {
            "window_hours": window_hours,
            "generated_signals": len(signal_rows),
            "scanner_decisions": len(scanner_rows),
            "notification_requests": sum(
                1 for row in notification_rows if row.get("event_type") == "requested"
            ),
            "delivered_notifications": sum(
                1 for row in notification_rows if row.get("event_type") == "delivered"
            ),
            "acknowledged_notifications": sum(
                1 for row in receipt_rows if row.get("event_type") == "acknowledged"
            ),
            "trade_actions": len(trade_rows),
            "subscriptions_started": len(subscription_rows),
            "tradingagents_terminals": len(ta_rows),
            "latest_event_at": latest,
        }

    async def query_distribution(self, window_hours: int = 24) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(hours=window_hours)
        notification_rows = await self.client.query_rows("notification_events", start_at=cutoff)
        receipt_rows = await self.client.query_rows("receipt_events", start_at=cutoff)

        requested_rows = [row for row in notification_rows if row.get("event_type") == "requested"]
        delivered_rows = [row for row in notification_rows if row.get("event_type") == "delivered"]
        acknowledged_rows = [row for row in receipt_rows if row.get("event_type") == "acknowledged"]

        channels: dict[str, dict[str, Any]] = defaultdict(lambda: {"requested": 0, "delivered": 0})
        for row in requested_rows:
            channel = str(row.get("channel") or "unknown")
            channels[channel]["requested"] += 1
        for row in delivered_rows:
            channel = str(row.get("channel") or "unknown")
            channels[channel]["delivered"] += 1

        requested_total = len(requested_rows)
        delivered_total = len(delivered_rows)
        acknowledged_total = len(acknowledged_rows)
        return {
            "window_hours": window_hours,
            "requested_total": requested_total,
            "delivered_total": delivered_total,
            "acknowledged_total": acknowledged_total,
            "pending_acknowledgements": max(0, requested_total - acknowledged_total),
            "delivery_rate": round(
                (delivered_total / requested_total * 100) if requested_total else 0.0, 4
            ),
            "acknowledgement_rate": round(
                (acknowledged_total / delivered_total * 100) if delivered_total else 0.0, 4
            ),
            "channels": [
                {"channel": channel, **values} for channel, values in sorted(channels.items())
            ],
        }

    async def query_strategy_health(self, window_hours: int = 168) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(hours=window_hours)
        strategy_rows = await self.client.query_rows(
            "strategy_health_events",
            start_at=cutoff,
            order_by="occurred_at",
            descending=True,
        )
        signal_rows = await self.client.query_rows("signal_events", start_at=cutoff)
        counts_by_strategy: dict[str, int] = defaultdict(int)
        for row in signal_rows:
            strategy = str(row.get("strategy") or "unknown")
            counts_by_strategy[strategy] += 1

        latest_by_strategy: dict[str, dict[str, Any]] = {}
        for row in strategy_rows:
            strategy_name = str(row.get("strategy_name") or "unknown")
            if strategy_name in latest_by_strategy:
                continue
            latest_by_strategy[strategy_name] = row

        strategies = []
        refreshed_at: datetime | None = None
        for row in latest_by_strategy.values():
            occurred_at = self._parse_datetime(row.get("occurred_at"))
            if refreshed_at is None or (occurred_at is not None and occurred_at > refreshed_at):
                refreshed_at = occurred_at
            evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
            strategies.append(
                {
                    "strategy_name": row.get("strategy_name") or "unknown",
                    "rank": int(row.get("rank") or 0),
                    "score": float(row.get("score") or 0.0),
                    "degradation": float(row.get("degradation") or 0.0),
                    "symbols_covered": int(row.get("symbols_covered") or 0),
                    "signals_generated": counts_by_strategy.get(
                        str(row.get("strategy_name") or "unknown"), 0
                    ),
                    "timeframe": row.get("timeframe") or "1d",
                    "stable": bool(row.get("stable", evidence.get("stable", True))),
                    "top_symbols": row.get("top_symbols") or evidence.get("top_symbols") or [],
                    "as_of_date": occurred_at,
                }
            )

        strategies.sort(key=lambda item: (item["rank"], -item["score"]))
        return {
            "window_hours": window_hours,
            "strategies": strategies,
            "refreshed_at": refreshed_at,
        }

    async def query_tradingagents_metrics(self, window_hours: int = 24) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(hours=window_hours)
        rows = await self.client.query_rows("tradingagents_events", start_at=cutoff)
        requested_rows = [row for row in rows if row.get("event_type") == "requested"]
        terminal_rows = [row for row in rows if row.get("event_type") == "terminal"]
        completed_total = sum(
            1 for row in terminal_rows if str(row.get("status") or "").lower() == "completed"
        )
        timeout_total = sum(
            1 for row in terminal_rows if str(row.get("status") or "").lower() == "timeout"
        )
        failed_only_total = sum(
            1 for row in terminal_rows if str(row.get("status") or "").lower() == "failed"
        )
        failed_total = sum(
            1
            for row in terminal_rows
            if str(row.get("status") or "").lower() in {"failed", "timeout"}
        )
        by_final_action: dict[str, int] = defaultdict(int)
        latencies: list[float] = []
        for row in terminal_rows:
            action = str(row.get("final_action") or "unknown").lower()
            by_final_action[action] += 1
            latency = row.get("latency_seconds")
            try:
                if latency not in (None, ""):
                    latencies.append(float(latency))
            except (TypeError, ValueError):
                continue

        terminal_total = len(terminal_rows)
        open_total = max(0, len(requested_rows) - terminal_total)
        return {
            "window_hours": window_hours,
            "requested_total": len(requested_rows),
            "terminal_total": terminal_total,
            "completed_total": completed_total,
            "failed_total": failed_total,
            "open_total": open_total,
            "success_rate": round(
                (completed_total / terminal_total * 100) if terminal_total else 0.0, 4
            ),
            "avg_latency_seconds": round(sum(latencies) / len(latencies), 4) if latencies else None,
            "by_status": {
                "pending": open_total,
                "submitted": 0,
                "running": 0,
                "completed": completed_total,
                "failed": failed_only_total,
                "timeout": timeout_total,
            },
            "by_final_action": dict(sorted(by_final_action.items())),
        }

    async def query_signal_results(self, window_hours: int = 24) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(hours=window_hours)
        signal_rows = await self.client.query_rows("signal_events", start_at=cutoff)
        trade_rows = await self.client.query_rows("trade_events", start_at=cutoff)

        strategies: dict[str, int] = defaultdict(int)
        market_regimes: dict[str, int] = defaultdict(int)
        trade_statuses: dict[str, int] = defaultdict(int)
        signals_by_symbol: dict[str, int] = defaultdict(int)
        trades_by_symbol: dict[str, int] = defaultdict(int)
        executed_by_symbol: dict[str, int] = defaultdict(int)

        for row in signal_rows:
            symbol = str(row.get("symbol") or "UNKNOWN").upper()
            strategy = str(row.get("strategy") or "unknown")
            market_regime = str(row.get("market_regime") or "unknown")
            signals_by_symbol[symbol] += 1
            strategies[strategy] += 1
            market_regimes[market_regime] += 1

        confirmed_trades = 0
        adjusted_trades = 0
        ignored_trades = 0
        expired_trades = 0
        pending_trades = 0
        for row in trade_rows:
            symbol = str(row.get("symbol") or "UNKNOWN").upper()
            status = str(row.get("status") or "unknown").lower()
            trades_by_symbol[symbol] += 1
            trade_statuses[status] += 1
            if status == "confirmed":
                confirmed_trades += 1
                executed_by_symbol[symbol] += 1
            elif status == "adjusted":
                adjusted_trades += 1
                executed_by_symbol[symbol] += 1
            elif status == "ignored":
                ignored_trades += 1
            elif status == "expired":
                expired_trades += 1
            elif status == "pending":
                pending_trades += 1

        signal_symbols = set(signals_by_symbol)
        trade_symbols = set(trades_by_symbol)
        overlapping_symbols = signal_symbols & trade_symbols
        total_signals = len(signal_rows)
        total_trade_actions = len(trade_rows)
        executed_trades = confirmed_trades + adjusted_trades

        symbol_alignment = []
        for symbol in sorted(
            overlapping_symbols,
            key=lambda item: (
                -(signals_by_symbol.get(item, 0) + trades_by_symbol.get(item, 0)),
                item,
            ),
        )[:8]:
            trade_actions = trades_by_symbol.get(symbol, 0)
            symbol_alignment.append(
                {
                    "symbol": symbol,
                    "signals_generated": signals_by_symbol.get(symbol, 0),
                    "trade_actions": trade_actions,
                    "executed_trades": executed_by_symbol.get(symbol, 0),
                    "execution_rate": round(
                        (executed_by_symbol.get(symbol, 0) / trade_actions * 100)
                        if trade_actions
                        else 0.0,
                        4,
                    ),
                }
            )

        return {
            "window_hours": window_hours,
            "generated_after": cutoff,
            "total_signals": total_signals,
            "total_trade_actions": total_trade_actions,
            "confirmed_trades": confirmed_trades,
            "adjusted_trades": adjusted_trades,
            "ignored_trades": ignored_trades,
            "expired_trades": expired_trades,
            "pending_trades": pending_trades,
            "trade_action_rate": round(
                (total_trade_actions / total_signals * 100) if total_signals else 0.0,
                4,
            ),
            "executed_trade_rate": round(
                (executed_trades / total_signals * 100) if total_signals else 0.0,
                4,
            ),
            "unique_signal_symbols": len(signal_symbols),
            "unique_trade_symbols": len(trade_symbols),
            "overlapping_symbols": len(overlapping_symbols),
            "signal_strategies": self._bucket_rows(strategies),
            "market_regimes": self._bucket_rows(market_regimes),
            "trade_statuses": self._bucket_rows(trade_statuses),
            "symbol_alignment": symbol_alignment,
            "comparable_field_sets": [
                {
                    "category": "live_signals",
                    "fields": [
                        "symbol",
                        "signal_type",
                        "strategy",
                        "strategy_window",
                        "market_regime",
                        "score",
                    ],
                    "note": "来自 signal.generated / signal_events。",
                },
                {
                    "category": "trade_actions",
                    "fields": [
                        "symbol",
                        "action",
                        "status",
                        "actual_price",
                        "actual_amount",
                    ],
                    "note": "来自 trade.action.recorded / trade_events；当前按窗口与 symbol 做近似对齐。",
                },
                {
                    "category": "backtests",
                    "fields": [
                        "symbol",
                        "strategy_name",
                        "timeframe",
                        "window_days",
                        "score",
                        "degradation",
                    ],
                    "note": "与 live signal 的可比字段已明确，但当前响应暂不直接联表 backtest_runs。",
                },
            ],
        }

    @classmethod
    def _latest_timestamp(cls, *row_sets: list[dict[str, Any]]) -> datetime | None:
        latest: datetime | None = None
        for rows in row_sets:
            for row in rows:
                timestamp = cls._parse_datetime(
                    row.get("occurred_at")
                    or row.get("recorded_at")
                    or row.get("created_at")
                    or row.get("as_of_date")
                )
                if timestamp is None:
                    continue
                if latest is None or timestamp > latest:
                    latest = timestamp
        return latest

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str) and value.strip():
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        return None

    @staticmethod
    def _bucket_rows(items: dict[str, int], limit: int = 8) -> list[dict[str, Any]]:
        return [
            {"key": key, "count": int(count)}
            for key, count in sorted(items.items(), key=lambda entry: (-entry[1], entry[0]))[:limit]
        ]
