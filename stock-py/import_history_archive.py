from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import logging
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.quality_service import OhlcvQualityService
from domains.market_data.repository import SymbolRepository
from infra.db.models.market_data import OhlcvAnomalyModel, OhlcvModel
from infra.db.models.symbols import SymbolModel
from infra.db.session import get_session_factory

logger = logging.getLogger(__name__)

DEFAULT_ARCHIVE_SOURCE = "history.archive.adjusted"
SYMBOL_PREVIEW_LIMIT = 20
PER_SYMBOL_PREVIEW_LIMIT = 20
ANOMALY_INSERT_BATCH_SIZE = 1000
# asyncpg enforces a stricter bind-parameter limit than PostgreSQL itself.
POSTGRES_PARAMETER_LIMIT = 32767
OHLCV_INSERT_PARAMETER_COUNT = 11
MAX_SAFE_OHLCV_BATCH_SIZE = 2500


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().upper()


def parse_symbols_arg(value: str | None) -> list[str]:
    if not value:
        return []
    seen: set[str] = set()
    symbols: list[str] = []
    for item in str(value).split(","):
        symbol = normalize_symbol(item)
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        symbols.append(symbol)
    return symbols


def _coerce_float(value: Any, *, field_name: str, default: float | None = None) -> float:
    if value in (None, ""):
        if default is not None:
            return default
        raise ValueError(f"{field_name} is required")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc


def _coerce_date(value: Any) -> datetime:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("date is required")
    try:
        parsed = datetime.strptime(raw, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must be YYYY-MM-DD") from exc
    return parsed.replace(tzinfo=UTC)


def _repair_open_price(opened: float, high: float, low: float, close: float) -> float:
    if opened > 0:
        return opened
    if min(high, low, close) > 0:
        return close
    return opened


def _normalize_ohlc_envelope(opened: float, high: float, low: float, close: float) -> tuple[float, float, float, float]:
    normalized_high = max(opened, high, low, close)
    normalized_low = min(opened, high, low, close)
    return opened, normalized_high, normalized_low, close


def normalize_history_row(
    raw: dict[str, Any],
    *,
    adjust_prices: bool = True,
) -> tuple[str, dict[str, Any]]:
    normalized = {str(key).strip().lower(): value for key, value in raw.items()}
    symbol = normalize_symbol(normalized.get("symbol"))
    if not symbol:
        raise ValueError("symbol is required")

    timestamp = _coerce_date(normalized.get("date"))
    opened = _coerce_float(normalized.get("open"), field_name="open")
    high = _coerce_float(normalized.get("high"), field_name="high")
    low = _coerce_float(normalized.get("low"), field_name="low")
    close = _coerce_float(normalized.get("close"), field_name="close")
    adj_close = _coerce_float(normalized.get("adj close"), field_name="adj close", default=close)
    volume = _coerce_float(normalized.get("volume"), field_name="volume", default=0.0)
    opened = _repair_open_price(opened, high, low, close)

    adjustment_factor = 1.0
    if adjust_prices and close > 0 and adj_close > 0:
        adjustment_factor = adj_close / close
    elif adjust_prices and close > 0 and adj_close <= 0:
        adj_close = close

    def adjusted(value: float) -> float:
        return round(value * adjustment_factor, 6)

    normalized_open = adjusted(opened) if adjust_prices else round(opened, 6)
    normalized_high = adjusted(high) if adjust_prices else round(high, 6)
    normalized_low = adjusted(low) if adjust_prices else round(low, 6)
    normalized_close = round(adj_close, 6) if adjust_prices else round(close, 6)
    normalized_open, normalized_high, normalized_low, normalized_close = _normalize_ohlc_envelope(
        normalized_open,
        normalized_high,
        normalized_low,
        normalized_close,
    )

    return symbol, {
        "timestamp": timestamp,
        "open": normalized_open,
        "high": normalized_high,
        "low": normalized_low,
        "close": normalized_close,
        "volume": volume,
    }


def _resolve_history_member(archive: zipfile.ZipFile) -> str:
    members = archive.namelist()
    for member in members:
        if member.lower().endswith("history.csv"):
            return member
    csv_members = [member for member in members if member.lower().endswith(".csv")]
    if len(csv_members) == 1:
        return csv_members[0]
    raise ValueError("Could not resolve a single history CSV member from archive")


def _record_found_symbol(stats: dict[str, Any], symbol: str) -> None:
    stats["symbols_found_count"] += 1
    if len(stats["symbols_found_preview"]) < SYMBOL_PREVIEW_LIMIT:
        stats["symbols_found_preview"].append(symbol)
    found_set = stats.get("_found_symbols_set")
    if isinstance(found_set, set):
        found_set.add(symbol)


def normalize_ohlcv_batch_size(value: int) -> int:
    requested = max(int(value), 1)
    calculated_limit = POSTGRES_PARAMETER_LIMIT // OHLCV_INSERT_PARAMETER_COUNT
    return max(1, min(requested, calculated_limit, MAX_SAFE_OHLCV_BATCH_SIZE))


def iter_archive_symbol_groups(
    zip_path: str | Path,
    *,
    target_symbols: set[str] | None,
    start_symbol: str | None,
    adjust_prices: bool,
    stats: dict[str, Any],
):
    current_symbol: str | None = None
    current_rows: list[dict[str, Any]] = []

    with zipfile.ZipFile(Path(zip_path)) as archive:
        member = _resolve_history_member(archive)
        with archive.open(member, "r") as handle:
            text_stream = io.TextIOWrapper(handle, encoding="utf-8-sig", newline="")
            reader = csv.DictReader(text_stream)
            fieldnames = {str(name).strip().lower() for name in (reader.fieldnames or [])}
            required_fields = {
                "date",
                "open",
                "high",
                "low",
                "close",
                "adj close",
                "volume",
                "symbol",
            }
            missing_fields = sorted(required_fields - fieldnames)
            if missing_fields:
                raise ValueError(
                    f"Archive CSV is missing required fields: {', '.join(missing_fields)}"
                )

            for raw in reader:
                stats["archive_rows_seen"] += 1
                try:
                    symbol, row = normalize_history_row(raw, adjust_prices=adjust_prices)
                except ValueError as exc:
                    stats["bad_rows"] += 1
                    if len(stats["bad_row_examples"]) < 5:
                        stats["bad_row_examples"].append(str(exc))
                    continue

                if start_symbol is not None and symbol < start_symbol:
                    continue

                if target_symbols is not None and symbol not in target_symbols:
                    continue

                stats["archive_rows_selected"] += 1

                if current_symbol is None:
                    current_symbol = symbol
                    _record_found_symbol(stats, symbol)
                elif current_symbol != symbol:
                    yield current_symbol, current_rows
                    current_symbol = symbol
                    current_rows = []
                    _record_found_symbol(stats, symbol)

                current_rows.append(row)

    if current_symbol is not None:
        yield current_symbol, current_rows


def collect_rows_by_symbol(
    zip_path: str | Path,
    *,
    target_symbols: set[str] | None,
    adjust_prices: bool = True,
) -> dict[str, Any]:
    rows_by_symbol: dict[str, list[dict[str, Any]]] = {}
    stats = {
        "archive_rows_seen": 0,
        "archive_rows_selected": 0,
        "bad_rows": 0,
        "bad_row_examples": [],
        "symbols_found_count": 0,
        "symbols_found_preview": [],
        "_found_symbols_set": set() if target_symbols is not None else None,
    }

    for symbol, rows in iter_archive_symbol_groups(
        zip_path,
        target_symbols=target_symbols,
        start_symbol=None,
        adjust_prices=adjust_prices,
        stats=stats,
    ):
        rows_by_symbol[symbol] = rows

    selected_symbols = sorted(rows_by_symbol.keys())
    missing_symbols = sorted((target_symbols or set()) - set(rows_by_symbol.keys()))
    return {
        "rows_by_symbol": rows_by_symbol,
        "rows_seen": stats["archive_rows_seen"],
        "rows_selected": stats["archive_rows_selected"],
        "bad_rows": stats["bad_rows"],
        "bad_row_examples": stats["bad_row_examples"],
        "selected_symbols": selected_symbols,
        "missing_symbols": missing_symbols,
    }


async def resolve_target_symbols(
    explicit_symbols: list[str],
    *,
    all_symbols: bool,
) -> tuple[list[str] | None, bool, str]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = SymbolRepository(session)
        if all_symbols:
            return None, False, "all"

        if explicit_symbols:
            await repository.bulk_upsert_symbols(
                [
                    {
                        "symbol": symbol,
                        "asset_type": "EQUITY",
                    }
                    for symbol in explicit_symbols
                ]
            )
            await session.commit()
            return explicit_symbols, False, "explicit"

        active_symbols = await repository.list_active_symbols(limit=5000)
        symbols = [normalize_symbol(record.symbol) for record in active_symbols if record.is_active]
        if symbols:
            await repository.bulk_upsert_symbols(
                [
                    {
                        "symbol": symbol,
                        "asset_type": "EQUITY",
                        "is_active": True,
                    }
                    for symbol in symbols
                ]
            )
            await session.commit()
        return symbols, True, "active"


async def load_symbol_cache(session: AsyncSession) -> dict[str, tuple[int, bool]]:
    result = await session.execute(select(SymbolModel.symbol, SymbolModel.id, SymbolModel.is_active))
    return {
        normalize_symbol(symbol): (int(symbol_id), bool(is_active))
        for symbol, symbol_id, is_active in result.all()
    }


async def ensure_symbol_record(
    session: AsyncSession,
    symbol_cache: dict[str, tuple[int, bool]],
    symbol: str,
    *,
    activate_new_symbols: bool,
) -> tuple[int, bool]:
    cached = symbol_cache.get(symbol)
    if cached is not None:
        return cached[0], False

    stmt = (
        pg_insert(SymbolModel)
        .values(
            {
                "symbol": symbol,
                "asset_type": "EQUITY",
                "is_active": activate_new_symbols,
            }
        )
        .on_conflict_do_nothing(index_elements=[SymbolModel.symbol])
        .returning(SymbolModel.id, SymbolModel.is_active)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        result = await session.execute(
            select(SymbolModel.id, SymbolModel.is_active).where(SymbolModel.symbol == symbol)
        )
        existing = result.first()
        if existing is None:
            raise RuntimeError(f"Failed to create or resolve symbol record for {symbol}")
        symbol_cache[symbol] = (int(existing.id), bool(existing.is_active))
        return int(existing.id), False

    symbol_id = int(row.id)
    symbol_cache[symbol] = (symbol_id, bool(row.is_active))
    return symbol_id, True


def normalize_for_quality(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "timestamp": row["timestamp"],
        "open": row["open"],
        "high": row["high"],
        "low": row["low"],
        "close": row["close"],
        "volume": row["volume"],
    }


async def bulk_upsert_ohlcv_rows(
    session: AsyncSession,
    *,
    symbol_id: int,
    symbol: str,
    timeframe: str,
    rows: list[dict[str, Any]],
    source: str,
    batch_size: int,
) -> int:
    imported_rows = 0
    normalized_timeframe = timeframe.strip().lower()
    effective_batch_size = normalize_ohlcv_batch_size(batch_size)

    for start in range(0, len(rows), effective_batch_size):
        batch = rows[start : start + effective_batch_size]
        payload = [
            {
                "symbol_id": symbol_id,
                "symbol": symbol,
                "timeframe": normalized_timeframe,
                "bar_time": row["timestamp"],
                "open": row["open"],
                "high": row["high"],
                "low": row["low"],
                "close": row["close"],
                "volume": row["volume"],
                "source": source,
            }
            for row in batch
        ]
        stmt = pg_insert(OhlcvModel).values(payload)
        excluded = stmt.excluded
        stmt = stmt.on_conflict_do_update(
            index_elements=[OhlcvModel.symbol, OhlcvModel.timeframe, OhlcvModel.bar_time],
            set_={
                "symbol_id": excluded.symbol_id,
                "open": excluded.open,
                "high": excluded.high,
                "low": excluded.low,
                "close": excluded.close,
                "volume": excluded.volume,
                "source": excluded.source,
                "imported_at": func.now(),
            },
        )
        await session.execute(stmt)
        imported_rows += len(batch)

    return imported_rows


async def bulk_insert_anomalies(
    session: AsyncSession,
    *,
    symbol: str,
    timeframe: str,
    anomalies: list[dict[str, Any]],
    source: str,
) -> int:
    if not anomalies:
        return 0

    inserted = 0
    normalized_timeframe = timeframe.strip().lower()
    for start in range(0, len(anomalies), ANOMALY_INSERT_BATCH_SIZE):
        batch = anomalies[start : start + ANOMALY_INSERT_BATCH_SIZE]
        payload = [
            {
                "symbol": symbol,
                "timeframe": normalized_timeframe,
                "bar_time": item.get("timestamp"),
                "anomaly_code": str(item.get("code") or "unknown"),
                "severity": str(item.get("severity") or "warning"),
                "details": json.dumps(item.get("details") or {}, default=str),
                "source": source,
            }
            for item in batch
        ]
        await session.execute(pg_insert(OhlcvAnomalyModel).values(payload))
        inserted += len(batch)

    return inserted


async def clear_existing_anomalies(
    *,
    source: str,
    target_symbols: list[str] | None,
) -> int:
    session_factory = get_session_factory()
    async with session_factory() as session:
        count_stmt = select(func.count()).select_from(OhlcvAnomalyModel).where(
            OhlcvAnomalyModel.source == source
        )
        delete_stmt = delete(OhlcvAnomalyModel).where(OhlcvAnomalyModel.source == source)
        if target_symbols is not None:
            count_stmt = count_stmt.where(OhlcvAnomalyModel.symbol.in_(target_symbols))
            delete_stmt = delete_stmt.where(OhlcvAnomalyModel.symbol.in_(target_symbols))

        existing = int(await session.scalar(count_stmt) or 0)
        if existing:
            await session.execute(delete_stmt)
            await session.commit()
        return existing


async def import_rows_streaming(
    zip_path: str | Path,
    *,
    target_symbols: list[str] | None,
    start_symbol: str | None,
    activate_new_symbols: bool,
    timeframe: str,
    source: str,
    batch_size: int,
    adjust_prices: bool,
    dry_run: bool,
    clear_existing_anomalies_first: bool,
) -> dict[str, Any]:
    selected_symbol_set = set(target_symbols) if target_symbols is not None else None
    scan_stats: dict[str, Any] = {
        "archive_rows_seen": 0,
        "archive_rows_selected": 0,
        "bad_rows": 0,
        "bad_row_examples": [],
        "symbols_found_count": 0,
        "symbols_found_preview": [],
        "_found_symbols_set": set(selected_symbol_set or []) if selected_symbol_set is not None else None,
        "symbols_imported": 0,
        "imported_rows": 0,
        "anomalies": 0,
        "new_symbols_created": 0,
        "per_symbol_preview": {},
    }

    if not dry_run and clear_existing_anomalies_first:
        scan_stats["deleted_existing_anomalies"] = await clear_existing_anomalies(
            source=source,
            target_symbols=target_symbols,
        )

    session_factory = get_session_factory()
    async with session_factory() as session:
        quality_service = OhlcvQualityService()
        symbol_cache = await load_symbol_cache(session)

        for symbol, rows in iter_archive_symbol_groups(
            zip_path,
            target_symbols=selected_symbol_set,
            start_symbol=start_symbol,
            adjust_prices=adjust_prices,
            stats=scan_stats,
        ):
            if not rows:
                continue

            quality_rows = [normalize_for_quality(row) for row in rows]
            report = quality_service.validate_batch(symbol, timeframe, quality_rows)
            valid_rows = report["valid_rows"]
            anomalies = report["anomalies"]
            symbol_imported = 0
            created_symbol = False

            if not dry_run:
                symbol_id, created_symbol = await ensure_symbol_record(
                    session,
                    symbol_cache,
                    symbol,
                    activate_new_symbols=activate_new_symbols,
                )
                symbol_imported = await bulk_upsert_ohlcv_rows(
                    session,
                    symbol_id=symbol_id,
                    symbol=symbol,
                    timeframe=timeframe,
                    rows=valid_rows,
                    source=source,
                    batch_size=batch_size,
                )
                await bulk_insert_anomalies(
                    session,
                    symbol=symbol,
                    timeframe=timeframe,
                    anomalies=anomalies,
                    source=source,
                )
                await session.commit()

            scan_stats["symbols_imported"] += 1
            scan_stats["imported_rows"] += symbol_imported if not dry_run else len(valid_rows)
            scan_stats["anomalies"] += len(anomalies)
            if created_symbol:
                scan_stats["new_symbols_created"] += 1

            if len(scan_stats["per_symbol_preview"]) < PER_SYMBOL_PREVIEW_LIMIT:
                scan_stats["per_symbol_preview"][symbol] = {
                    "selected_rows": len(rows),
                    "imported_rows": symbol_imported if not dry_run else len(valid_rows),
                    "anomalies": len(anomalies),
                    "first_date": rows[0]["timestamp"].date().isoformat(),
                    "last_date": rows[-1]["timestamp"].date().isoformat(),
                    "symbol_created": created_symbol,
                }

            if scan_stats["symbols_imported"] % 100 == 0:
                logger.info(
                    "Archive import progress scope=%s symbols=%s rows=%s anomalies=%s",
                    "all" if selected_symbol_set is None else "filtered",
                    scan_stats["symbols_imported"],
                    scan_stats["imported_rows"],
                    scan_stats["anomalies"],
                )

    found_set = scan_stats.pop("_found_symbols_set", None)
    if selected_symbol_set is not None:
        if isinstance(found_set, set):
            missing_symbols = sorted(selected_symbol_set - found_set)
        else:
            missing_symbols = sorted(selected_symbol_set)
    else:
        missing_symbols = []

    return {
        "archive_rows_seen": scan_stats["archive_rows_seen"],
        "archive_rows_selected": scan_stats["archive_rows_selected"],
        "bad_rows": scan_stats["bad_rows"],
        "bad_row_examples": scan_stats["bad_row_examples"],
        "symbols_found_count": scan_stats["symbols_found_count"],
        "symbols_found_preview": scan_stats["symbols_found_preview"],
        "missing_symbols": missing_symbols,
        "symbols_imported": scan_stats["symbols_imported"],
        "imported_rows": scan_stats["imported_rows"],
        "anomalies": scan_stats["anomalies"],
        "new_symbols_created": scan_stats["new_symbols_created"],
        "per_symbol_preview": scan_stats["per_symbol_preview"],
        "deleted_existing_anomalies": int(scan_stats.get("deleted_existing_anomalies", 0) or 0),
    }


async def fetch_coverage(symbols: list[str] | None, *, timeframe: str) -> dict[str, Any]:
    normalized_timeframe = timeframe.strip().lower()

    session_factory = get_session_factory()
    async with session_factory() as session:
        aggregate_stmt = select(
            func.count().label("row_count"),
            func.count(func.distinct(OhlcvModel.symbol)).label("symbol_count"),
            func.min(OhlcvModel.bar_time).label("first_bar_time"),
            func.max(OhlcvModel.bar_time).label("last_bar_time"),
        ).where(OhlcvModel.timeframe == normalized_timeframe)
        if symbols is not None:
            aggregate_stmt = aggregate_stmt.where(OhlcvModel.symbol.in_(symbols))

        aggregate = (await session.execute(aggregate_stmt)).one()

        preview_stmt = (
            select(
                OhlcvModel.symbol,
                func.count().label("row_count"),
                func.min(OhlcvModel.bar_time).label("first_bar_time"),
                func.max(OhlcvModel.bar_time).label("last_bar_time"),
            )
            .where(OhlcvModel.timeframe == normalized_timeframe)
            .group_by(OhlcvModel.symbol)
            .order_by(OhlcvModel.symbol.asc())
            .limit(PER_SYMBOL_PREVIEW_LIMIT)
        )
        if symbols is not None:
            preview_stmt = preview_stmt.where(OhlcvModel.symbol.in_(symbols))
        preview_rows = (await session.execute(preview_stmt)).all()

        symbol_count_total = await session.scalar(select(func.count()).select_from(SymbolModel))
        active_symbol_count = await session.scalar(
            select(func.count()).select_from(SymbolModel).where(SymbolModel.is_active.is_(True))
        )

    return {
        "row_count": int(aggregate.row_count or 0),
        "symbol_count": int(aggregate.symbol_count or 0),
        "first_bar_time": aggregate.first_bar_time.isoformat() if aggregate.first_bar_time else None,
        "last_bar_time": aggregate.last_bar_time.isoformat() if aggregate.last_bar_time else None,
        "symbols_table_count": int(symbol_count_total or 0),
        "active_symbols_count": int(active_symbol_count or 0),
        "preview": {
            row.symbol: {
                "rows": int(row.row_count or 0),
                "first_bar_time": row.first_bar_time.isoformat() if row.first_bar_time else None,
                "last_bar_time": row.last_bar_time.isoformat() if row.last_bar_time else None,
            }
            for row in preview_rows
        },
    }


async def run_import(args: argparse.Namespace) -> dict[str, Any]:
    explicit_symbols = parse_symbols_arg(args.symbols)
    start_symbol = normalize_symbol(args.start_symbol) if args.start_symbol else None
    target_symbols, activate_new_symbols, import_scope = await resolve_target_symbols(
        explicit_symbols,
        all_symbols=bool(args.all_symbols),
    )
    import_summary = await import_rows_streaming(
        args.zip_path,
        target_symbols=target_symbols,
        start_symbol=start_symbol,
        activate_new_symbols=activate_new_symbols,
        timeframe=args.timeframe,
        source=args.source,
        batch_size=args.batch_size,
        adjust_prices=not args.no_adjust_prices,
        dry_run=bool(args.dry_run),
        clear_existing_anomalies_first=not bool(args.preserve_existing_anomalies),
    )

    result: dict[str, Any] = {
        "zip_path": str(Path(args.zip_path).resolve()),
        "timeframe": args.timeframe,
        "source": args.source,
        "requested_batch_size": int(args.batch_size),
        "effective_batch_size": normalize_ohlcv_batch_size(args.batch_size),
        "import_scope": import_scope,
        "start_symbol": start_symbol,
        "target_symbol_count": len(target_symbols) if target_symbols is not None else None,
        "target_symbols": target_symbols if target_symbols is not None and len(target_symbols) <= 50 else None,
        "dry_run": bool(args.dry_run),
        **import_summary,
    }

    if args.dry_run:
        return result

    result["coverage"] = await fetch_coverage(
        target_symbols if import_scope != "all" else None,
        timeframe=args.timeframe,
    )
    return result


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Import a zipped Yahoo-style history.csv archive into stock-py OHLCV storage.",
    )
    parser.add_argument(
        "zip_path",
        nargs="?",
        default="/mnt/c/Users/nico_/Downloads/history.csv.zip",
        help="Path to history.csv.zip",
    )
    parser.add_argument(
        "--symbols",
        default="",
        help="Comma-separated symbol list. Defaults to current active symbols in the database.",
    )
    parser.add_argument(
        "--all-symbols",
        action="store_true",
        help="Import every symbol present in the archive. New symbol records are created inactive by default.",
    )
    parser.add_argument(
        "--start-symbol",
        default="",
        help="Resume from the specified symbol (inclusive). Archive ordering is alphabetical by symbol.",
    )
    parser.add_argument("--timeframe", default="1d", help="Target timeframe, default: 1d")
    parser.add_argument(
        "--source",
        default=DEFAULT_ARCHIVE_SOURCE,
        help=f"Stored source label, default: {DEFAULT_ARCHIVE_SOURCE}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Import batch size per symbol, default: 5000",
    )
    parser.add_argument(
        "--no-adjust-prices",
        action="store_true",
        help="Store raw OHLC instead of scaling OHLC to Adj Close.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and align archive rows without writing to the database.",
    )
    parser.add_argument(
        "--preserve-existing-anomalies",
        action="store_true",
        help="Do not delete existing anomaly rows for this source before importing.",
    )
    return parser


def main() -> int:
    parser = build_argument_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    result = asyncio.run(run_import(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())