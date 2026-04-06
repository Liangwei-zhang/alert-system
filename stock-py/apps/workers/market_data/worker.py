from __future__ import annotations

import asyncio
import inspect
import logging
from typing import Any, Sequence

from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


class MarketDataWorker:
    def __init__(
        self,
        *,
        poll_interval_seconds: int = 900,
        source: str = "yahoo",
        sync_queries: Sequence[str] = (),
        timeframes: Sequence[str] = ("1d",),
        history_period: str = "3mo",
        symbol_loader: Any | None = None,
        history_loader: Any | None = None,
    ) -> None:
        self.poll_interval = poll_interval_seconds
        self.source = source
        self.sync_queries = tuple(sync_queries)
        self.timeframes = tuple(timeframes)
        self.history_period = history_period
        self.symbol_loader = symbol_loader
        self.history_loader = history_loader
        self._running = False

    async def run_forever(self, initial_delay: float = 5.0) -> None:
        logger.info("Starting market data worker")
        await asyncio.sleep(initial_delay)
        self._running = True
        while self._running:
            try:
                await self.run_once()
            except Exception:
                logger.exception("Market data worker cycle failed")
            await asyncio.sleep(self.poll_interval)
        logger.info("Market data worker stopped")

    async def run_once(
        self, *, sync_queries: Sequence[str] | None = None, symbols: Sequence[str] | None = None
    ) -> dict[str, int]:
        sync_result = await self.sync_symbols(sync_queries=sync_queries)
        import_result = await self.import_ohlcv(symbols=symbols)
        quality_result = await self.run_quality_checks(symbols=symbols)
        return {
            "synced": sync_result["synced"],
            "imported": import_result["imported"],
            "anomalies": import_result["anomalies"] + quality_result["anomalies"],
            "validated": quality_result["validated"],
        }

    async def sync_symbols(self, *, sync_queries: Sequence[str] | None = None) -> dict[str, int]:
        from domains.market_data.symbol_sync_service import SymbolSyncService

        queries = tuple(sync_queries) if sync_queries is not None else self.sync_queries
        if not queries:
            return {"synced": 0}

        session = await self.open_session()
        try:
            service = SymbolSyncService(session, source_loader=self.symbol_loader)
            total = 0
            for query in queries:
                result = await service.sync_symbols(query=query, source=self.source)
                total += int(result["synced_count"])
            await self.commit_session(session)
            return {"synced": total}
        finally:
            await self.close_session(session)

    async def import_ohlcv(self, *, symbols: Sequence[str] | None = None) -> dict[str, int]:
        from domains.market_data.ohlcv_import_service import OhlcvImportService

        session = await self.open_session()
        try:
            resolved_symbols = (
                list(symbols) if symbols is not None else await self._list_active_symbols(session)
            )
            imported = 0
            anomalies = 0
            service = OhlcvImportService(session)
            for symbol in resolved_symbols:
                for timeframe in self.timeframes:
                    bars = await self._load_history(symbol, timeframe)
                    if not bars:
                        continue
                    result = await service.import_batch(
                        symbol, timeframe, bars, source="marketdata.worker"
                    )
                    imported += int(result["imported_count"])
                    anomalies += int(result["anomaly_count"])
            await self.commit_session(session)
            return {"imported": imported, "anomalies": anomalies}
        finally:
            await self.close_session(session)

    async def run_quality_checks(self, *, symbols: Sequence[str] | None = None) -> dict[str, int]:
        from domains.market_data.quality_service import OhlcvQualityService
        from domains.market_data.repository import OhlcvRepository

        session = await self.open_session()
        try:
            resolved_symbols = (
                list(symbols) if symbols is not None else await self._list_active_symbols(session)
            )
            repository = OhlcvRepository(session)
            quality = OhlcvQualityService()
            validated = 0
            anomalies = 0
            for symbol in resolved_symbols:
                for timeframe in self.timeframes:
                    bars = await repository.get_recent_bars(symbol, timeframe=timeframe, limit=60)
                    if not bars:
                        continue
                    report = quality.validate_batch(symbol, timeframe, bars)
                    validated += int(report["stats"]["valid_count"])
                    anomalies += int(report["stats"]["anomaly_count"])
            return {"validated": validated, "anomalies": anomalies}
        finally:
            await self.close_session(session)

    async def open_session(self) -> Any:
        from infra.db.session import get_session_factory

        session_factory = get_session_factory()
        return session_factory()

    async def close_session(self, session: Any) -> None:
        close = getattr(session, "close", None)
        if callable(close):
            result = close()
            if inspect.isawaitable(result):
                await result

    async def commit_session(self, session: Any) -> None:
        commit = getattr(session, "commit", None)
        if callable(commit):
            result = commit()
            if inspect.isawaitable(result):
                await result

    async def _list_active_symbols(self, session: Any) -> list[str]:
        from domains.market_data.repository import SymbolRepository

        records = await SymbolRepository(session).list_active_symbols(limit=500)
        return [record.symbol for record in records]

    async def _load_history(self, symbol: str, timeframe: str) -> list[dict[str, Any]]:
        if self.history_loader is not None:
            result = self.history_loader(symbol, timeframe, self.history_period, self.source)
            if inspect.isawaitable(result):
                result = await result
            return [self._normalize_history_item(item) for item in result]

        from infra.market_data.data_source import MarketDataSourceFactory

        bars = await MarketDataSourceFactory.get_historical(
            symbol, self.history_period, source=self.source
        )
        return [self._normalize_history_item(item) for item in bars]

    @staticmethod
    def _normalize_history_item(item: Any) -> dict[str, Any]:
        if isinstance(item, dict):
            return dict(item)
        return {
            "date": getattr(item, "date"),
            "open": getattr(item, "open"),
            "high": getattr(item, "high"),
            "low": getattr(item, "low"),
            "close": getattr(item, "close"),
            "volume": getattr(item, "volume", 0),
        }

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "market-data",
        "worker",
        MarketDataWorker().run_once,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Market data cycle finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
