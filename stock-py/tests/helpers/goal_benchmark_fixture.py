from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from infra.db.models.backtest import StrategyRankingModel
from infra.db.models.base import Base
from infra.db.models.market_data import OhlcvModel
from infra.db.models.symbols import SymbolModel

SYMBOLS: tuple[str, ...] = (
    'AAPL',
    'MSFT',
    'NVDA',
    'AMZN',
    'META',
    'AVGO',
    'LLY',
    'COST',
)

DEFAULT_DATABASE_URL = 'sqlite+aiosqlite:///./.local/benchmarks/live-strategy-goal-ci.sqlite3'
DEFAULT_SOURCE = 'history.archive.adjusted'
DEFAULT_TIMEFRAME = '1d'
DEFAULT_BAR_COUNT = 120


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Seed a deterministic benchmark fixture for run_live_strategy_goal_benchmark.py.',
    )
    parser.add_argument(
        '--database-url',
        default=os.environ.get('DATABASE_URL', DEFAULT_DATABASE_URL),
        help='Target SQLAlchemy database URL.',
    )
    parser.add_argument('--timeframe', default=DEFAULT_TIMEFRAME)
    parser.add_argument('--source', default=DEFAULT_SOURCE)
    parser.add_argument('--bar-count', type=int, default=DEFAULT_BAR_COUNT)
    return parser


def ensure_database_parent(database_url: str) -> None:
    url = make_url(database_url)
    if not str(url.drivername).startswith('sqlite') or not url.database:
        return
    Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def build_trend_bars(symbol: str, *, symbol_index: int, bar_count: int, timeframe: str, source: str) -> list[dict[str, Any]]:
    bars: list[dict[str, Any]] = []
    current_price = 100.0 + (symbol_index * 6.5)
    start_at = datetime(2025, 1, 6, tzinfo=UTC) + timedelta(days=symbol_index)

    for offset in range(bar_count):
        base_drift = 0.55 + (symbol_index * 0.025)
        tailwind = 0.18 if offset >= (bar_count - 30) else 0.0
        cycle = (((offset + symbol_index) % 6) - 2.5) * 0.08
        open_price = max(0.01, current_price - 0.16 + (cycle * 0.25))
        close_price = max(0.01, current_price + base_drift + tailwind + cycle)
        high_price = max(open_price, close_price) + 0.34 + ((offset % 3) * 0.03)
        low_price = max(0.01, min(open_price, close_price) - 0.24 - ((offset % 2) * 0.02))
        volume = 1_000_000 + (offset * 1_500) + (symbol_index * 22_000)
        bars.append(
            {
                'symbol': symbol,
                'timeframe': timeframe,
                'bar_time': start_at + timedelta(days=offset),
                'open': round(open_price, 6),
                'high': round(high_price, 6),
                'low': round(low_price, 6),
                'close': round(close_price, 6),
                'volume': round(volume, 4),
                'source': source,
            }
        )
        current_price = close_price

    return bars


def build_ranking_rows(*, symbol_count: int, timeframe: str) -> list[StrategyRankingModel]:
    as_of_date = datetime(2026, 4, 12, 9, 30, tzinfo=UTC)
    definitions = (
        ('trend_following', 1, 24.0, 0.4, True),
        ('breakout', 2, 16.5, 1.8, True),
        ('mean_reversion', 3, 6.0, 8.8, False),
        ('rsi_reversion', 4, 4.5, 9.5, False),
        ('bollinger_reversion', 5, 3.8, 10.1, False),
        ('buy_and_hold', 6, 7.5, 0.2, True),
        ('sma_cross', 7, 5.2, 0.7, True),
    )
    top_symbols = [
        {'symbol': symbol, 'score': round(1.4 - (index * 0.08), 4)}
        for index, symbol in enumerate(SYMBOLS[:5])
    ]

    rows: list[StrategyRankingModel] = []
    for strategy_name, rank, score, degradation, stable in definitions:
        evidence = {
            'stable': stable,
            'best_window_days': 90,
            'windows': {
                '30': {'score': round(score * 1.02, 4)},
                '90': {'score': round(score, 4)},
                '180': {'score': round(score * 0.96, 4)},
            },
            'top_symbols': top_symbols,
        }
        rows.append(
            StrategyRankingModel(
                strategy_name=strategy_name,
                timeframe=timeframe,
                rank=rank,
                score=score,
                degradation=degradation,
                symbols_covered=symbol_count,
                evidence=json.dumps(evidence, ensure_ascii=True),
                as_of_date=as_of_date,
            )
        )
    return rows


async def seed_fixture(database_url: str, *, timeframe: str, source: str, bar_count: int) -> dict[str, Any]:
    ensure_database_parent(database_url)
    engine = create_async_engine(database_url, future=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.drop_all(
                sync_connection,
                tables=[OhlcvModel.__table__, StrategyRankingModel.__table__, SymbolModel.__table__],
            )
        )
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[SymbolModel.__table__, OhlcvModel.__table__, StrategyRankingModel.__table__],
            )
        )

    async with session_factory() as session:
        symbol_rows = [
            SymbolModel(
                symbol=symbol,
                name=f'{symbol} Fixture',
                asset_type='EQUITY',
                exchange='FIXTURE',
                is_active=True,
            )
            for symbol in SYMBOLS
        ]
        session.add_all(symbol_rows)
        await session.flush()

        bars_inserted = 0
        for index, symbol_row in enumerate(symbol_rows):
            bars = build_trend_bars(
                symbol_row.symbol,
                symbol_index=index,
                bar_count=bar_count,
                timeframe=timeframe,
                source=source,
            )
            session.add_all(
                [
                    OhlcvModel(
                        symbol_id=symbol_row.id,
                        symbol=bar['symbol'],
                        timeframe=bar['timeframe'],
                        bar_time=bar['bar_time'],
                        open=bar['open'],
                        high=bar['high'],
                        low=bar['low'],
                        close=bar['close'],
                        volume=bar['volume'],
                        source=bar['source'],
                    )
                    for bar in bars
                ]
            )
            bars_inserted += len(bars)

        ranking_rows = build_ranking_rows(symbol_count=len(symbol_rows), timeframe=timeframe)
        session.add_all(ranking_rows)
        await session.commit()

    await engine.dispose()

    return {
        'database_url': database_url,
        'symbol_count': len(SYMBOLS),
        'bar_count_per_symbol': bar_count,
        'bars_inserted': bars_inserted,
        'ranking_count': len(ranking_rows),
        'timeframe': timeframe,
        'source': source,
        'symbols': list(SYMBOLS),
    }


def main() -> int:
    args = build_parser().parse_args()
    summary = asyncio.run(
        seed_fixture(
            args.database_url,
            timeframe=str(args.timeframe).strip().lower() or DEFAULT_TIMEFRAME,
            source=str(args.source).strip() or DEFAULT_SOURCE,
            bar_count=max(int(args.bar_count), 60),
        )
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())