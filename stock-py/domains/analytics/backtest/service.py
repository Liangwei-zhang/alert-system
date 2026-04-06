from __future__ import annotations

import math
from statistics import mean, pstdev
from typing import Any, Iterable


class NullPublisher:
    async def publish_after_commit(
        self,
        topic: str,
        payload: dict[str, Any],
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        del headers
        return {"topic": topic, "payload": payload, "key": key}


class BacktestService:
    DEFAULT_WINDOWS = (30, 90, 180, 365)
    DEFAULT_STRATEGIES = ("trend_following", "mean_reversion", "breakout")

    def __init__(
        self,
        session: Any = None,
        *,
        repository: Any | None = None,
        symbol_provider: Any | None = None,
        publisher: Any | None = None,
    ) -> None:
        self.session = session
        self.repository = repository
        self.symbol_provider = symbol_provider
        self.publisher = publisher

    async def refresh_rankings(
        self,
        *,
        symbols: list[str] | None = None,
        strategy_names: Iterable[str] | None = None,
        windows: Iterable[int] | None = None,
        timeframe: str = "1d",
    ) -> dict[str, Any]:
        repository = self._get_repository()
        resolved_symbols = [
            symbol.strip().upper()
            for symbol in (symbols or await self._list_symbols())
            if symbol.strip()
        ]
        resolved_strategies = tuple(strategy_names or self.DEFAULT_STRATEGIES)
        resolved_windows = tuple(int(window) for window in (windows or self.DEFAULT_WINDOWS))

        run = await repository.save_run(
            {
                "strategy_name": "ranking_refresh",
                "symbol": "*",
                "timeframe": timeframe,
                "window_days": max(resolved_windows) if resolved_windows else 0,
                "status": "running",
                "summary": {"symbols": resolved_symbols, "strategies": list(resolved_strategies)},
            }
        )

        rankings: list[dict[str, Any]] = []
        for strategy_name in resolved_strategies:
            per_window: dict[int, dict[str, Any]] = {}
            for window_days in resolved_windows:
                window_results: list[dict[str, Any]] = []
                for symbol in resolved_symbols:
                    result = await self.run_backtest_window(
                        symbol=symbol,
                        window_days=window_days,
                        strategy_name=strategy_name,
                        timeframe=timeframe,
                    )
                    if result is None:
                        continue
                    window_results.append(result)

                aggregate_metrics = self._aggregate_window_results(window_results)
                if aggregate_metrics is None:
                    continue
                score = self._ranking_score(aggregate_metrics)
                top_symbols = sorted(
                    (
                        {
                            "symbol": item["symbol"],
                            "return_percent": item["metrics"]["total_return_percent"],
                            "trade_count": item["metrics"]["trade_count"],
                        }
                        for item in window_results
                    ),
                    key=lambda item: item["return_percent"],
                    reverse=True,
                )[:5]
                per_window[window_days] = {
                    "score": score,
                    "symbols_covered": len(window_results),
                    "metrics": aggregate_metrics,
                    "top_symbols": top_symbols,
                }

            if not per_window:
                continue

            degradation = self.calculate_degradation(
                {window: payload["score"] for window, payload in per_window.items()}
            )
            evidence = self.build_strategy_evidence(strategy_name, per_window, degradation)
            overall_score = round(
                mean(payload["score"] for payload in per_window.values()) - degradation, 4
            )
            rankings.append(
                {
                    "strategy_name": strategy_name,
                    "timeframe": timeframe,
                    "score": overall_score,
                    "degradation": degradation,
                    "symbols_covered": sum(
                        payload["symbols_covered"] for payload in per_window.values()
                    ),
                    "evidence": evidence,
                }
            )

        rankings.sort(key=lambda item: item["score"], reverse=True)
        for index, item in enumerate(rankings, start=1):
            item["rank"] = index

        saved_rankings = await repository.save_rankings(rankings)
        summary = {
            "ranking_count": len(rankings),
            "top_strategy": rankings[0]["strategy_name"] if rankings else None,
            "symbols_covered": len(resolved_symbols),
        }
        await repository.save_results(
            run,
            {
                "status": "completed",
                "summary": summary,
                "metrics": {"rankings": rankings},
                "evidence": {"strategies": [item["strategy_name"] for item in rankings]},
            },
        )
        await self._publish_refresh(summary, rankings, timeframe=timeframe)
        return {
            "run_id": int(getattr(run, "id", run)),
            "ranking_count": len(saved_rankings),
            "rankings": rankings,
        }

    async def run_backtest_window(
        self,
        *,
        symbol: str,
        window_days: int,
        strategy_name: str,
        timeframe: str = "1d",
    ) -> dict[str, Any] | None:
        bars = await self._get_repository().load_window_data(symbol, window_days, timeframe)
        if len(bars) < 20:
            return None

        cash = 1.0
        equity = 1.0
        peak_equity = 1.0
        max_drawdown = 0.0
        in_position = False
        entry_price = 0.0
        entry_index = 0
        trades: list[dict[str, Any]] = []
        equity_points: list[float] = []

        for index in range(20, len(bars)):
            price = float(bars[index]["close"])
            signal = self._evaluate_strategy(strategy_name, bars, index)

            if in_position:
                mark_equity = cash * (price / entry_price) if entry_price else cash
            else:
                mark_equity = cash
            peak_equity = max(peak_equity, mark_equity)
            max_drawdown = max(
                max_drawdown, (peak_equity - mark_equity) / peak_equity if peak_equity else 0.0
            )
            equity_points.append(mark_equity)

            if not in_position and signal == "buy":
                in_position = True
                entry_price = price
                entry_index = index
                continue

            if in_position and signal == "sell":
                trade_return = ((price / entry_price) - 1.0) if entry_price else 0.0
                cash *= 1.0 + trade_return
                equity = cash
                trades.append(
                    {
                        "entry_index": entry_index,
                        "exit_index": index,
                        "entry_price": entry_price,
                        "exit_price": price,
                        "return_percent": trade_return * 100,
                    }
                )
                in_position = False
                entry_price = 0.0

        if in_position and entry_price:
            final_price = float(bars[-1]["close"])
            trade_return = (final_price / entry_price) - 1.0
            cash *= 1.0 + trade_return
            equity = cash
            trades.append(
                {
                    "entry_index": entry_index,
                    "exit_index": len(bars) - 1,
                    "entry_price": entry_price,
                    "exit_price": final_price,
                    "return_percent": trade_return * 100,
                }
            )

        trade_returns = [trade["return_percent"] for trade in trades]
        total_return_percent = (equity - 1.0) * 100
        win_rate = (
            (sum(1 for value in trade_returns if value > 0) / len(trade_returns) * 100)
            if trade_returns
            else 0.0
        )
        avg_trade_return_percent = mean(trade_returns) if trade_returns else 0.0
        volatility = pstdev(trade_returns) if len(trade_returns) > 1 else 0.0
        sharpe_ratio = (
            (avg_trade_return_percent / volatility * math.sqrt(len(trade_returns)))
            if volatility > 0
            else 0.0
        )

        metrics = {
            "total_return_percent": round(total_return_percent, 4),
            "max_drawdown_percent": round(max_drawdown * 100, 4),
            "trade_count": len(trades),
            "win_rate": round(win_rate, 4),
            "avg_trade_return_percent": round(avg_trade_return_percent, 4),
            "sharpe_ratio": round(sharpe_ratio, 4),
            "samples": len(bars),
        }
        return {
            "symbol": symbol.strip().upper(),
            "strategy_name": strategy_name,
            "window_days": window_days,
            "timeframe": timeframe,
            "metrics": metrics,
            "trades": trades,
            "equity_points": equity_points,
        }

    def calculate_degradation(self, scores_by_window: dict[int, float]) -> float:
        if len(scores_by_window) < 2:
            return 0.0
        ordered = sorted(scores_by_window.items())
        shortest_score = ordered[0][1]
        longest_score = ordered[-1][1]
        degradation = max(0.0, shortest_score - longest_score)
        spread = max(scores_by_window.values()) - min(scores_by_window.values())
        return round((degradation * 0.7) + (spread * 0.3), 4)

    def build_strategy_evidence(
        self,
        strategy_name: str,
        window_payloads: dict[int, dict[str, Any]],
        degradation: float,
    ) -> dict[str, Any]:
        ordered = sorted(window_payloads.items())
        best_window_days, best_window = max(ordered, key=lambda item: item[1]["score"])
        weakest_window_days, weakest_window = min(ordered, key=lambda item: item[1]["score"])
        return {
            "strategy_name": strategy_name,
            "best_window_days": best_window_days,
            "best_score": best_window["score"],
            "weakest_window_days": weakest_window_days,
            "weakest_score": weakest_window["score"],
            "degradation": degradation,
            "stable": degradation < 5.0,
            "windows": {
                str(window): {
                    "score": payload["score"],
                    "symbols_covered": payload["symbols_covered"],
                    "top_symbols": payload["top_symbols"],
                    "metrics": payload["metrics"],
                }
                for window, payload in ordered
            },
        }

    def _aggregate_window_results(self, results: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not results:
            return None
        metrics_list = [item["metrics"] for item in results]
        return {
            "total_return_percent": round(
                mean(metric["total_return_percent"] for metric in metrics_list), 4
            ),
            "max_drawdown_percent": round(
                mean(metric["max_drawdown_percent"] for metric in metrics_list), 4
            ),
            "trade_count": int(sum(metric["trade_count"] for metric in metrics_list)),
            "win_rate": round(mean(metric["win_rate"] for metric in metrics_list), 4),
            "avg_trade_return_percent": round(
                mean(metric["avg_trade_return_percent"] for metric in metrics_list), 4
            ),
            "sharpe_ratio": round(mean(metric["sharpe_ratio"] for metric in metrics_list), 4),
            "samples": int(sum(metric["samples"] for metric in metrics_list)),
        }

    def _ranking_score(self, metrics: dict[str, Any]) -> float:
        return round(
            (metrics["total_return_percent"] * 0.45)
            + (metrics["win_rate"] * 0.2)
            + (metrics["sharpe_ratio"] * 8.0)
            - (metrics["max_drawdown_percent"] * 0.35)
            + min(metrics["trade_count"], 20) * 0.4,
            4,
        )

    async def _publish_refresh(
        self, summary: dict[str, Any], rankings: list[dict[str, Any]], *, timeframe: str
    ) -> None:
        publisher = self._get_publisher()
        await publisher.publish_after_commit(
            topic="ops.audit.logged",
            key=f"backtest:{timeframe}",
            payload={
                "entity": "backtest",
                "entity_id": timeframe,
                "action": "rankings.refreshed",
                "summary": summary,
                "top_strategy": rankings[0]["strategy_name"] if rankings else None,
            },
        )
        await publisher.publish_after_commit(
            topic="strategy.rankings.refreshed",
            key=f"strategy:{timeframe}",
            payload={
                "timeframe": timeframe,
                "summary": summary,
                "rankings": rankings,
            },
        )

    async def _list_symbols(self) -> list[str]:
        if self.symbol_provider is not None:
            result = self.symbol_provider()
            if hasattr(result, "__await__"):
                result = await result
            return [str(item).strip().upper() for item in result if str(item).strip()]
        if self.session is None:
            return []
        from domains.market_data.repository import SymbolRepository

        records = await SymbolRepository(self.session).list_active_symbols(limit=200)
        return [record.symbol for record in records]

    def _get_repository(self) -> Any:
        if self.repository is not None:
            return self.repository
        if self.session is None:
            raise RuntimeError("BacktestService requires a session or repository")
        from domains.analytics.backtest.repository import BacktestRepository

        self.repository = BacktestRepository(self.session)
        return self.repository

    def _get_publisher(self) -> Any:
        if self.publisher is not None:
            return self.publisher
        if self.session is None:
            self.publisher = NullPublisher()
            return self.publisher
        from infra.events.outbox import OutboxPublisher

        self.publisher = OutboxPublisher(self.session)
        return self.publisher

    def _evaluate_strategy(
        self, strategy_name: str, bars: list[dict[str, Any]], index: int
    ) -> str | None:
        closes = [float(bar["close"]) for bar in bars[: index + 1]]
        highs = [float(bar["high"]) for bar in bars[: index + 1]]
        lows = [float(bar["low"]) for bar in bars[: index + 1]]
        current = closes[-1]
        sma5 = mean(closes[-5:])
        sma10 = mean(closes[-10:])
        sma20 = mean(closes[-20:])
        prev_sma10 = mean(closes[-11:-1])
        prev_sma20 = mean(closes[-21:-1])
        std20 = pstdev(closes[-20:]) if len(closes) >= 20 else 0.0
        breakout_high = max(highs[-21:-1])
        breakdown_low = min(lows[-11:-1])

        if strategy_name == "trend_following":
            if current > sma10 > sma20 and (current - closes[-2]) > 0:
                return "buy"
            if current < sma10 or sma10 < sma20:
                return "sell"
            return None

        if strategy_name == "mean_reversion":
            if current < sma20 - (std20 * 1.5):
                return "buy"
            if current >= sma20 or current > sma5:
                return "sell"
            return None

        if strategy_name == "breakout":
            if current > breakout_high:
                return "buy"
            if current < sma10 or current < breakdown_low:
                return "sell"
            return None

        if current > sma20:
            return "buy"
        if current < sma20:
            return "sell"
        return None
