from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from statistics import mean
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.analytics.backtest.experiment_tracking import capture_code_version
from domains.analytics.backtest.service import BacktestService
from domains.market_data.scanner_snapshot_service import ScannerSnapshotService
from domains.signals.live_strategy_engine import LiveStrategyEngine
from infra.db.models.backtest import StrategyRankingModel
from infra.db.models.market_data import OhlcvModel
from infra.db.session import get_session_factory

logger = logging.getLogger(__name__)

DEFAULT_TIMEFRAME = "1d"
DEFAULT_SOURCE = "history.archive.adjusted"
DEFAULT_LIMIT = 200
DEFAULT_MIN_BARS = 365
DEFAULT_LOOKBACK_BARS = 365
DEFAULT_TEST_BARS = 90
DEFAULT_RANKING_WINDOWS = (30, 90, 180)
DEFAULT_BASELINE = "legacy_heuristic"
DEFAULT_RANKING_SOURCE = "latest_substantial_db"
DEFAULT_SUBSTANTIAL_RANKING_COUNT = 7
DEFAULT_SUBSTANTIAL_SYMBOLS_COVERED = 100
TARGET_NEW_WIN_RATE = 65.58
TARGET_ABSOLUTE_UPLIFT = 10.89
TARGET_RELATIVE_UPLIFT = 19.92

LIVE_TO_BACKTEST_STRATEGY = {
    "breakout": "breakout",
    "mean_reversion": "mean_reversion",
    "range_rotation": "rsi_reversion",
    "trend_continuation": "trend_following",
    "volatility_breakout": "breakout",
}


def parse_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_windows(value: str | None) -> tuple[int, ...]:
    parsed = [int(item) for item in parse_csv_values(value)]
    return tuple(parsed or DEFAULT_RANKING_WINDOWS)


async def select_symbol_universe(
    *,
    session: AsyncSession,
    timeframe: str,
    source: str | None,
    min_bars: int,
    limit: int | None,
) -> list[str]:
    statement = (
        select(OhlcvModel.symbol, func.count().label("bar_count"))
        .where(OhlcvModel.timeframe == timeframe.strip().lower())
        .group_by(OhlcvModel.symbol)
        .having(func.count() >= int(min_bars))
        .order_by(func.count().desc(), OhlcvModel.symbol.asc())
    )
    if source:
        statement = statement.where(OhlcvModel.source == source)
    if limit:
        statement = statement.limit(int(limit))

    rows = (await session.execute(statement)).all()
    return [str(row.symbol).strip().upper() for row in rows]


async def load_recent_bars(
    session: AsyncSession,
    *,
    symbol: str,
    timeframe: str,
    source: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    statement = (
        select(OhlcvModel)
        .where(
            OhlcvModel.symbol == symbol.strip().upper(),
            OhlcvModel.timeframe == timeframe.strip().lower(),
        )
        .order_by(OhlcvModel.bar_time.desc())
        .limit(limit)
    )
    if source:
        statement = statement.where(OhlcvModel.source == source)

    result = await session.execute(statement)
    rows = list(result.scalars().all())
    rows.reverse()
    return [
        {
            "timestamp": row.bar_time,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
            "volume": float(row.volume),
            "symbol": row.symbol,
            "timeframe": row.timeframe,
            "source": row.source,
        }
        for row in rows
    ]


async def load_latest_substantial_ranking_batch(
    session: AsyncSession,
    *,
    timeframe: str,
    min_ranking_count: int,
    min_symbols_covered: int,
) -> dict[str, Any] | None:
    latest_as_of = (
        await session.execute(
            select(StrategyRankingModel.as_of_date)
            .where(StrategyRankingModel.timeframe == timeframe.strip().lower())
            .group_by(StrategyRankingModel.as_of_date)
            .having(
                func.count() >= int(min_ranking_count),
                func.max(StrategyRankingModel.symbols_covered) >= int(min_symbols_covered),
            )
            .order_by(StrategyRankingModel.as_of_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_as_of is None:
        return None

    rows = list(
        (
            await session.execute(
                select(StrategyRankingModel)
                .where(
                    StrategyRankingModel.timeframe == timeframe.strip().lower(),
                    StrategyRankingModel.as_of_date == latest_as_of,
                )
                .order_by(StrategyRankingModel.rank.asc(), StrategyRankingModel.id.asc())
            )
        ).scalars().all()
    )
    rankings = [
        {
            "strategy_name": row.strategy_name,
            "timeframe": row.timeframe,
            "rank": row.rank,
            "score": float(row.score),
            "degradation": float(row.degradation),
            "symbols_covered": int(row.symbols_covered or 0),
            "evidence": json.loads(row.evidence) if row.evidence else {},
        }
        for row in rows
    ]
    return {
        "as_of_date": latest_as_of,
        "ranking_count": len(rankings),
        "rankings": rankings,
    }


def resolve_concrete_strategy(strategy_name: str) -> str:
    normalized = str(strategy_name or "").strip().lower()
    return LIVE_TO_BACKTEST_STRATEGY.get(normalized, normalized or "rsi_reversion")


def resolve_legacy_heuristic_strategy(snapshot: dict[str, Any]) -> str:
    dislocation = abs(float(snapshot.get("dislocation_pct") or 0.0))
    momentum = float(snapshot.get("momentum_score") or 0.0)
    volatility = float(snapshot.get("volatility_score") or 0.0)

    if dislocation >= 0.03:
        return "mean_reversion"
    if momentum >= 0.65:
        return "trend_following"
    if volatility >= 0.75:
        return "breakout"
    return "rsi_reversion"


def resolve_baseline_strategy(baseline: str, snapshot: dict[str, Any]) -> str:
    normalized = str(baseline or DEFAULT_BASELINE).strip().lower()
    if normalized == "legacy_heuristic":
        return resolve_legacy_heuristic_strategy(snapshot)
    return "rsi_reversion"


def aggregate_trade_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    trades = [trade for result in results for trade in list(result.get("trades") or [])]
    trade_count = len(trades)
    winning_trades = sum(1 for trade in trades if float(trade.get("return_percent") or 0.0) > 0)
    return {
        "symbol_count": len(results),
        "trade_count": trade_count,
        "winning_trades": winning_trades,
        "win_rate": round((winning_trades / trade_count * 100.0) if trade_count else 0.0, 4),
        "mean_total_return_percent": round(
            mean(float(result["metrics"].get("total_return_percent") or 0.0) for result in results),
            4,
        )
        if results
        else 0.0,
        "mean_trade_count_per_symbol": round((trade_count / len(results)) if results else 0.0, 4),
    }


def calculate_relative_uplift_percent(*, new_win_rate: float, baseline_win_rate: float) -> float | None:
    if baseline_win_rate <= 0:
        return None if new_win_rate > baseline_win_rate else 0.0
    return round(((new_win_rate - baseline_win_rate) / baseline_win_rate) * 100.0, 4)


def build_goal_evaluation(
    *,
    new_win_rate: float,
    baseline_win_rate: float,
    target_new_win_rate: float,
    target_absolute_uplift: float,
    target_relative_uplift: float,
) -> dict[str, Any]:
    absolute_uplift = round(new_win_rate - baseline_win_rate, 4)
    relative_uplift = calculate_relative_uplift_percent(
        new_win_rate=new_win_rate,
        baseline_win_rate=baseline_win_rate,
    )
    relative_check: dict[str, Any] = {
        "actual": relative_uplift,
        "target": round(target_relative_uplift, 4),
        "passed": (
            new_win_rate > baseline_win_rate
            if relative_uplift is None
            else relative_uplift >= round(target_relative_uplift, 4)
        ),
    }
    if relative_uplift is None:
        relative_check["basis"] = "baseline_win_rate_zero"

    checks = {
        "new_win_rate": {
            "actual": round(new_win_rate, 4),
            "target": round(target_new_win_rate, 4),
            "passed": round(new_win_rate, 4) >= round(target_new_win_rate, 4),
        },
        "absolute_uplift_pp": {
            "actual": absolute_uplift,
            "target": round(target_absolute_uplift, 4),
            "passed": absolute_uplift >= round(target_absolute_uplift, 4),
        },
        "relative_uplift_percent": relative_check,
    }
    return {
        "met": all(item["passed"] for item in checks.values()),
        "checks": checks,
    }


def build_rankings_from_training_data(
    *,
    service: BacktestService,
    training_bars_by_symbol: dict[str, list[dict[str, Any]]],
    timeframe: str,
    ranking_windows: tuple[int, ...],
) -> list[dict[str, Any]]:
    rankings: list[dict[str, Any]] = []
    for strategy_name in service.SUPPORTED_STRATEGIES:
        per_window: dict[int, dict[str, Any]] = {}
        for window_days in ranking_windows:
            window_results: list[dict[str, Any]] = []
            for symbol, train_bars in training_bars_by_symbol.items():
                result = service._run_backtest_from_bars(
                    symbol=symbol,
                    window_days=window_days,
                    strategy_name=strategy_name,
                    timeframe=timeframe,
                    bars=service._slice_bars_to_window(train_bars, window_days),
                )
                if result is None:
                    continue
                window_results.append(result)

            aggregate_metrics = service._aggregate_window_results(window_results)
            if aggregate_metrics is None:
                continue

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
                "score": service._ranking_score(aggregate_metrics),
                "symbols_covered": len(window_results),
                "metrics": aggregate_metrics,
                "top_symbols": top_symbols,
            }

        if not per_window:
            continue

        degradation = service.calculate_degradation(
            {window: payload["score"] for window, payload in per_window.items()}
        )
        evidence = service.build_strategy_evidence(strategy_name, per_window, degradation)
        overall_score = round(
            mean(payload["score"] for payload in per_window.values()) - degradation,
            4,
        )
        rankings.append(
            {
                "strategy_name": strategy_name,
                "timeframe": timeframe,
                "score": overall_score,
                "degradation": degradation,
                "symbols_covered": sum(payload["symbols_covered"] for payload in per_window.values()),
                "evidence": evidence,
            }
        )

    rankings.sort(key=lambda item: item["score"], reverse=True)
    for index, ranking in enumerate(rankings, start=1):
        ranking["rank"] = index
    return rankings


async def run_goal_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    if args.test_bars >= args.lookback_bars:
        raise RuntimeError("test bars must be smaller than lookback bars")

    session_factory = get_session_factory()
    service = BacktestService()
    engine = LiveStrategyEngine()
    snapshot_service = ScannerSnapshotService()
    timeframe = args.timeframe.strip().lower()
    ranking_windows = tuple(window for window in parse_windows(args.ranking_windows) if window > 0)
    ranking_batch_meta: dict[str, Any] | None = None

    async with session_factory() as session:
        symbols = await select_symbol_universe(
            session=session,
            timeframe=timeframe,
            source=args.source or None,
            min_bars=args.min_bars,
            limit=args.limit,
        )
        if not symbols:
            raise RuntimeError("No symbols matched the requested benchmark universe")

        bars_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for symbol in symbols:
            bars = await load_recent_bars(
                session,
                symbol=symbol,
                timeframe=timeframe,
                source=args.source or None,
                limit=args.lookback_bars,
            )
            if len(bars) >= args.lookback_bars:
                bars_by_symbol[symbol] = bars

        if args.ranking_source == "latest_substantial_db":
            ranking_batch_meta = await load_latest_substantial_ranking_batch(
                session,
                timeframe=timeframe,
                min_ranking_count=args.substantial_ranking_count,
                min_symbols_covered=args.substantial_symbols_covered,
            )

    if not bars_by_symbol:
        raise RuntimeError("No symbols had enough recent bars for the goal benchmark")

    training_bars_by_symbol = {
        symbol: bars[: args.lookback_bars - args.test_bars]
        for symbol, bars in bars_by_symbol.items()
        if len(bars) >= args.lookback_bars
    }
    test_bars_by_symbol = {
        symbol: bars[-args.test_bars :]
        for symbol, bars in bars_by_symbol.items()
        if len(bars) >= args.lookback_bars
    }

    if args.ranking_source == "latest_substantial_db":
        if ranking_batch_meta is None:
            raise RuntimeError(
                "No substantial persisted ranking batch was found; rerun benchmark rankings or use --ranking-source train_window"
            )
        rankings = list(ranking_batch_meta["rankings"])
    else:
        rankings = build_rankings_from_training_data(
            service=service,
            training_bars_by_symbol=training_bars_by_symbol,
            timeframe=timeframe,
            ranking_windows=ranking_windows,
        )
        ranking_batch_meta = {
            "ranking_count": len(rankings),
            "ranking_windows": list(ranking_windows),
        }
    if not rankings:
        raise RuntimeError("Unable to build training rankings for the goal benchmark")

    baseline_results: list[dict[str, Any]] = []
    new_results: list[dict[str, Any]] = []
    baseline_results_by_symbol: dict[str, dict[str, Any]] = {}
    published_symbols: list[str] = []
    suppressed_records: list[dict[str, Any]] = []
    skipped_symbols: list[dict[str, Any]] = []

    for symbol, train_bars in training_bars_by_symbol.items():
        test_bars = test_bars_by_symbol[symbol]
        snapshot = snapshot_service.build_snapshot(symbol, train_bars, timeframe=timeframe)
        if snapshot is None:
            skipped_symbols.append({"symbol": symbol, "reason": "snapshot_unavailable"})
            continue

        baseline_strategy = resolve_baseline_strategy(args.baseline, snapshot)
        baseline_result = service._run_backtest_from_bars(
            symbol=symbol,
            window_days=args.test_bars,
            strategy_name=baseline_strategy,
            timeframe=timeframe,
            bars=test_bars,
        )
        if baseline_result is not None:
            baseline_results.append(baseline_result)
            baseline_results_by_symbol[symbol] = baseline_result

        selection = engine.select_strategy(
            symbol,
            {
                **snapshot,
                "strategy_rankings": rankings,
            },
            context={"timeframe": timeframe},
        )
        alert_decision = selection.get("alert_decision") if isinstance(selection, dict) else None
        if isinstance(alert_decision, dict) and not alert_decision.get("publish_allowed", True):
            suppressed_records.append(
                {
                    "symbol": symbol,
                    "selection_strategy": selection.get("strategy"),
                    "source_strategy": selection.get("source_strategy"),
                    "suppressed_reasons": list(alert_decision.get("suppressed_reasons") or []),
                }
            )
            continue

        concrete_strategy = resolve_concrete_strategy(
            str(selection.get("source_strategy") or selection.get("strategy") or "")
        )
        new_result = service._run_backtest_from_bars(
            symbol=symbol,
            window_days=args.test_bars,
            strategy_name=concrete_strategy,
            timeframe=timeframe,
            bars=test_bars,
        )
        if new_result is None:
            skipped_symbols.append(
                {
                    "symbol": symbol,
                    "reason": "new_strategy_unavailable",
                    "strategy": concrete_strategy,
                }
            )
            continue
        published_symbols.append(symbol)
        new_results.append(new_result)

    baseline_metrics = aggregate_trade_metrics(baseline_results)
    new_metrics = aggregate_trade_metrics(new_results)
    suppressed_subset_metrics = aggregate_trade_metrics(
        [
            baseline_results_by_symbol[item["symbol"]]
            for item in suppressed_records
            if item["symbol"] in baseline_results_by_symbol
        ]
    )
    published_subset_metrics = aggregate_trade_metrics(
        [baseline_results_by_symbol[symbol] for symbol in published_symbols if symbol in baseline_results_by_symbol]
    )
    goal = build_goal_evaluation(
        new_win_rate=float(new_metrics["win_rate"]),
        baseline_win_rate=float(baseline_metrics["win_rate"]),
        target_new_win_rate=args.target_new_win_rate,
        target_absolute_uplift=args.target_absolute_uplift,
        target_relative_uplift=args.target_relative_uplift,
    )
    relative_uplift_percent = calculate_relative_uplift_percent(
        new_win_rate=float(new_metrics["win_rate"]),
        baseline_win_rate=float(baseline_metrics["win_rate"]),
    )

    report = {
        "timeframe": timeframe,
        "source": args.source,
        "baseline": args.baseline,
        "ranking_source": args.ranking_source,
        "goal": goal,
        "comparison": {
            "baseline_win_rate": baseline_metrics["win_rate"],
            "new_win_rate": new_metrics["win_rate"],
            "absolute_uplift_pp": round(new_metrics["win_rate"] - baseline_metrics["win_rate"], 4),
            "relative_uplift_percent": relative_uplift_percent,
            "relative_uplift_basis": (
                "baseline_win_rate_zero"
                if relative_uplift_percent is None and new_metrics["win_rate"] > baseline_metrics["win_rate"]
                else None
            ),
        },
        "universe": {
            "requested_limit": args.limit,
            "eligible_symbol_count": len(bars_by_symbol),
            "symbol_preview": list(bars_by_symbol)[:20],
            "lookback_bars": args.lookback_bars,
            "train_bars": args.lookback_bars - args.test_bars,
            "test_bars": args.test_bars,
            "min_bars": args.min_bars,
        },
        "baseline_metrics": baseline_metrics,
        "new_metrics": {
            **new_metrics,
            "published_symbol_count": len(published_symbols),
            "suppressed_symbol_count": len(suppressed_records),
        },
        "suppression_diagnostics": {
            "suppressed_symbols": suppressed_records,
            "baseline_on_suppressed_subset": suppressed_subset_metrics,
            "baseline_on_published_subset": published_subset_metrics,
        },
        "ranking_batch": ranking_batch_meta,
        "rankings_preview": rankings[:5],
        "skipped_symbols": skipped_symbols,
        "code_version": capture_code_version(),
    }
    return report


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the archive-backed live strategy goal benchmark and enforce win-rate targets.",
    )
    parser.add_argument("--timeframe", default=DEFAULT_TIMEFRAME, help="Target timeframe, default: 1d")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Optional source filter for symbol universe selection, default: {DEFAULT_SOURCE}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Universe size cap after eligibility filtering, default: {DEFAULT_LIMIT}",
    )
    parser.add_argument(
        "--min-bars",
        type=int,
        default=DEFAULT_MIN_BARS,
        help=f"Minimum bars required per symbol, default: {DEFAULT_MIN_BARS}",
    )
    parser.add_argument(
        "--lookback-bars",
        type=int,
        default=DEFAULT_LOOKBACK_BARS,
        help=f"Recent bars loaded per symbol, default: {DEFAULT_LOOKBACK_BARS}",
    )
    parser.add_argument(
        "--test-bars",
        type=int,
        default=DEFAULT_TEST_BARS,
        help=f"Out-of-sample test bars at the end of the lookback window, default: {DEFAULT_TEST_BARS}",
    )
    parser.add_argument(
        "--ranking-windows",
        default=",".join(str(item) for item in DEFAULT_RANKING_WINDOWS),
        help="Comma-separated training ranking windows, default: 30,90,180",
    )
    parser.add_argument(
        "--baseline",
        choices=("rsi_proxy", "legacy_heuristic"),
        default=DEFAULT_BASELINE,
        help="Baseline used for comparison, default: legacy_heuristic",
    )
    parser.add_argument(
        "--ranking-source",
        choices=("latest_substantial_db", "train_window"),
        default=DEFAULT_RANKING_SOURCE,
        help="Where ranking inputs come from, default: latest_substantial_db",
    )
    parser.add_argument(
        "--substantial-ranking-count",
        type=int,
        default=DEFAULT_SUBSTANTIAL_RANKING_COUNT,
        help=f"Minimum ranking rows required for a persisted batch to be treated as substantial, default: {DEFAULT_SUBSTANTIAL_RANKING_COUNT}",
    )
    parser.add_argument(
        "--substantial-symbols-covered",
        type=int,
        default=DEFAULT_SUBSTANTIAL_SYMBOLS_COVERED,
        help=f"Minimum symbols_covered required for a persisted batch to be treated as substantial, default: {DEFAULT_SUBSTANTIAL_SYMBOLS_COVERED}",
    )
    parser.add_argument(
        "--target-new-win-rate",
        type=float,
        default=TARGET_NEW_WIN_RATE,
        help=f"Minimum new-logic win rate target, default: {TARGET_NEW_WIN_RATE}",
    )
    parser.add_argument(
        "--target-absolute-uplift",
        type=float,
        default=TARGET_ABSOLUTE_UPLIFT,
        help=f"Minimum absolute uplift target in percentage points, default: {TARGET_ABSOLUTE_UPLIFT}",
    )
    parser.add_argument(
        "--target-relative-uplift",
        type=float,
        default=TARGET_RELATIVE_UPLIFT,
        help=f"Minimum relative uplift target in percent, default: {TARGET_RELATIVE_UPLIFT}",
    )
    parser.add_argument(
        "--allow-goal-miss",
        action="store_true",
        help="Return exit code 0 even when the benchmark misses one or more goal thresholds.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional JSON report output path.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    report = asyncio.run(run_goal_benchmark(args))
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    if report["goal"]["met"] or args.allow_goal_miss:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())