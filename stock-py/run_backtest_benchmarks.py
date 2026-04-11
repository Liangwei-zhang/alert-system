from __future__ import annotations

import argparse
import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any

from sqlalchemy import func, select

from domains.analytics.backtest.service import BacktestService
from infra.db.models.market_data import OhlcvModel
from infra.db.session import get_session_factory

logger = logging.getLogger(__name__)

DEFAULT_SOURCE = "history.archive.adjusted"
DEFAULT_MIN_BARS = 250
DEFAULT_WINDOWS = (90, 180, 365)
DEFAULT_STRATEGIES = BacktestService.DEFAULT_STRATEGIES + BacktestService.BASELINE_STRATEGIES


def parse_csv_values(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_windows(value: str | None) -> tuple[int, ...]:
    parsed = [int(item) for item in parse_csv_values(value)]
    return tuple(parsed or DEFAULT_WINDOWS)


async def select_symbol_universe(
    *,
    timeframe: str,
    source: str | None,
    min_bars: int,
    limit: int | None,
) -> list[str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
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


async def run_benchmarks(args: argparse.Namespace) -> dict[str, Any]:
    strategies = parse_csv_values(args.strategies) or list(DEFAULT_STRATEGIES)
    windows = parse_windows(args.windows)
    artifact_entries = [
        {
            "type": "cli",
            "name": "benchmark_report",
            "locator": {
                "uri": uri,
            },
        }
        for uri in list(getattr(args, "artifact_uri", []) or [])
        if str(uri).strip()
    ]
    symbols = await select_symbol_universe(
        timeframe=args.timeframe,
        source=args.source or None,
        min_bars=args.min_bars,
        limit=args.limit,
    )
    if not symbols:
        raise RuntimeError("No symbols matched the requested benchmark universe")

    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await BacktestService(session).refresh_rankings(
            symbols=symbols,
            strategy_names=strategies,
            windows=windows,
            timeframe=args.timeframe,
            experiment_name=args.experiment_name,
            experiment_context={
                "trigger": "cli",
                "entrypoint": "run_backtest_benchmarks.py",
                "dataset": {
                    "limit": args.limit or None,
                    "min_bars": args.min_bars,
                    "selection_mode": "archive_benchmark",
                    "source": args.source or None,
                },
            },
            artifact_entries=artifact_entries,
        )
        await session.commit()

    return {
        "timeframe": args.timeframe,
        "source": args.source,
        "min_bars": args.min_bars,
        "symbol_count": len(symbols),
        "symbol_preview": symbols[:20],
        "strategies": strategies,
        "windows": list(windows),
        "result": result,
    }


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run baseline and internal strategy rankings over an archive-backed symbol universe.",
    )
    parser.add_argument("--timeframe", default="1d", help="Target timeframe, default: 1d")
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help=f"Optional source filter for symbol universe selection, default: {DEFAULT_SOURCE}",
    )
    parser.add_argument(
        "--min-bars",
        type=int,
        default=DEFAULT_MIN_BARS,
        help=f"Minimum bars required per symbol, default: {DEFAULT_MIN_BARS}",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional cap on universe size after ranking symbol eligibility.",
    )
    parser.add_argument(
        "--strategies",
        default=",".join(DEFAULT_STRATEGIES),
        help="Comma-separated strategy names or aliases.",
    )
    parser.add_argument(
        "--windows",
        default=",".join(str(item) for item in DEFAULT_WINDOWS),
        help="Comma-separated backtest windows in days.",
    )
    parser.add_argument(
        "--experiment-name",
        default="cli.backtest-benchmarks",
        help="Experiment name to attach to the saved backtest run.",
    )
    parser.add_argument(
        "--artifact-uri",
        action="append",
        default=[],
        help="Optional artifact URI to include in the experiment record. Repeatable.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    result = asyncio.run(run_benchmarks(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())