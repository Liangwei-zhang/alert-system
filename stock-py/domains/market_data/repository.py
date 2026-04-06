from __future__ import annotations

import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.market_data import OhlcvAnomalyModel, OhlcvModel, SymbolModel


class SymbolRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert_symbols(self, items: list[dict[str, Any]]) -> list[SymbolModel]:
        symbols = [
            str(item["symbol"]).strip().upper()
            for item in items
            if str(item.get("symbol", "")).strip()
        ]
        if not symbols:
            return []

        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.symbol.in_(symbols))
        )
        existing_by_symbol = {record.symbol.upper(): record for record in result.scalars().all()}
        saved: list[SymbolModel] = []

        for item in items:
            symbol = str(item.get("symbol", "")).strip().upper()
            if not symbol:
                continue
            record = existing_by_symbol.get(symbol)
            if record is None:
                record = SymbolModel(symbol=symbol)
                self.session.add(record)
                existing_by_symbol[symbol] = record
            record.name = item.get("name") or record.name
            record.name_zh = item.get("name_zh") or record.name_zh
            record.asset_type = item.get("asset_type") or record.asset_type
            record.exchange = item.get("exchange") or record.exchange
            record.sector = item.get("sector") or record.sector
            if item.get("is_active") is not None:
                record.is_active = bool(item.get("is_active"))
            saved.append(record)

        await self.session.flush()
        return saved

    async def get_symbol(self, symbol: str) -> SymbolModel | None:
        result = await self.session.execute(
            select(SymbolModel).where(SymbolModel.symbol == symbol.strip().upper())
        )
        return result.scalar_one_or_none()

    async def list_active_symbols(self, limit: int = 500) -> list[SymbolModel]:
        result = await self.session.execute(
            select(SymbolModel)
            .where(SymbolModel.is_active.is_(True))
            .order_by(SymbolModel.symbol.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class OhlcvRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def bulk_upsert_bars(
        self,
        symbol: str,
        timeframe: str,
        rows: list[dict[str, Any]],
        source: str | None = None,
    ) -> list[OhlcvModel]:
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip().lower()
        timestamps = [row["timestamp"] for row in rows]
        existing_by_time: dict[Any, OhlcvModel] = {}
        if timestamps:
            result = await self.session.execute(
                select(OhlcvModel).where(
                    OhlcvModel.symbol == normalized_symbol,
                    OhlcvModel.timeframe == normalized_timeframe,
                    OhlcvModel.bar_time.in_(timestamps),
                )
            )
            existing_by_time = {record.bar_time: record for record in result.scalars().all()}

        symbol_id = await self._resolve_symbol_id(normalized_symbol)
        saved: list[OhlcvModel] = []
        for row in rows:
            record = existing_by_time.get(row["timestamp"])
            if record is None:
                record = OhlcvModel(
                    symbol=normalized_symbol,
                    timeframe=normalized_timeframe,
                    bar_time=row["timestamp"],
                )
                self.session.add(record)
            record.symbol_id = symbol_id
            record.open = float(row["open"])
            record.high = float(row["high"])
            record.low = float(row["low"])
            record.close = float(row["close"])
            record.volume = float(row.get("volume", 0) or 0)
            record.source = source or row.get("source")
            saved.append(record)

        await self.session.flush()
        return saved

    async def quarantine_bad_rows(
        self,
        symbol: str,
        timeframe: str,
        anomalies: list[dict[str, Any]],
        source: str | None = None,
    ) -> list[OhlcvAnomalyModel]:
        records: list[OhlcvAnomalyModel] = []
        normalized_symbol = symbol.strip().upper()
        normalized_timeframe = timeframe.strip().lower()
        for item in anomalies:
            record = OhlcvAnomalyModel(
                symbol=normalized_symbol,
                timeframe=normalized_timeframe,
                bar_time=item.get("timestamp"),
                anomaly_code=str(item.get("code") or "unknown"),
                severity=str(item.get("severity") or "warning"),
                details=(
                    json.dumps(item.get("details") or {}, default=str)
                    if item.get("details")
                    else None
                ),
                source=source,
            )
            self.session.add(record)
            records.append(record)
        await self.session.flush()
        return records

    async def get_recent_bars(
        self,
        symbol: str,
        timeframe: str = "1d",
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        result = await self.session.execute(
            select(OhlcvModel)
            .where(
                OhlcvModel.symbol == symbol.strip().upper(),
                OhlcvModel.timeframe == timeframe.strip().lower(),
            )
            .order_by(OhlcvModel.bar_time.desc())
            .limit(limit)
        )
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

    async def list_anomalies(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        symbol: str | None = None,
        timeframe: str | None = None,
        severity: str | None = None,
        anomaly_code: str | None = None,
        source: str | None = None,
    ) -> list[OhlcvAnomalyModel]:
        statement = select(OhlcvAnomalyModel)
        if symbol:
            statement = statement.where(OhlcvAnomalyModel.symbol == symbol.strip().upper())
        if timeframe:
            statement = statement.where(OhlcvAnomalyModel.timeframe == timeframe.strip().lower())
        if severity:
            statement = statement.where(OhlcvAnomalyModel.severity == severity.strip().lower())
        if anomaly_code:
            statement = statement.where(
                OhlcvAnomalyModel.anomaly_code == anomaly_code.strip().lower()
            )
        if source:
            statement = statement.where(OhlcvAnomalyModel.source == source.strip())
        result = await self.session.execute(
            statement.order_by(OhlcvAnomalyModel.quarantined_at.desc(), OhlcvAnomalyModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_anomalies(
        self,
        *,
        symbol: str | None = None,
        timeframe: str | None = None,
        severity: str | None = None,
        anomaly_code: str | None = None,
        source: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(OhlcvAnomalyModel)
        if symbol:
            statement = statement.where(OhlcvAnomalyModel.symbol == symbol.strip().upper())
        if timeframe:
            statement = statement.where(OhlcvAnomalyModel.timeframe == timeframe.strip().lower())
        if severity:
            statement = statement.where(OhlcvAnomalyModel.severity == severity.strip().lower())
        if anomaly_code:
            statement = statement.where(
                OhlcvAnomalyModel.anomaly_code == anomaly_code.strip().lower()
            )
        if source:
            statement = statement.where(OhlcvAnomalyModel.source == source.strip())
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def _resolve_symbol_id(self, symbol: str) -> int | None:
        result = await self.session.execute(select(SymbolModel).where(SymbolModel.symbol == symbol))
        record = result.scalar_one_or_none()
        return int(record.id) if record is not None else None
