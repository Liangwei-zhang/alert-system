from __future__ import annotations

import zlib
from collections.abc import Iterable


class ActiveSymbolsService:
    def __init__(self, session) -> None:
        self.session = session
        self._projection: set[str] = set()
        self._dirty_symbols: set[str] = set()

    async def refresh_projection(self) -> list[str]:
        from sqlalchemy import select

        from infra.db.models.portfolio import PortfolioPositionModel
        from infra.db.models.watchlist import WatchlistItemModel

        watchlist_result = await self.session.execute(
            select(WatchlistItemModel.symbol).where(WatchlistItemModel.notify.is_(True))
        )
        portfolio_result = await self.session.execute(
            select(PortfolioPositionModel.symbol).where(PortfolioPositionModel.notify.is_(True))
        )
        merged = list(watchlist_result.scalars().all()) + list(portfolio_result.scalars().all())
        self._projection = set(self.normalize_symbols(merged)) | set(
            self.normalize_symbols(self._dirty_symbols)
        )
        self._dirty_symbols.clear()
        return sorted(self._projection)

    async def list_scan_buckets(self, bucket_count: int = 32):
        symbols = sorted(self._projection or set(await self.refresh_projection()))
        bucket_map = self.build_bucket_map(symbols, bucket_count)

        from domains.signals.schemas import ScannerBucketItem

        items = []
        for bucket_id in sorted(bucket_map):
            for priority, symbol in enumerate(bucket_map[bucket_id], start=1):
                items.append(
                    ScannerBucketItem(
                        bucket_id=bucket_id,
                        symbol=symbol,
                        priority=max(1, bucket_count - priority + 1),
                    )
                )
        return items

    def mark_symbol_dirty(self, symbol: str) -> str:
        normalized = self.normalize_symbols([symbol])[0]
        self._dirty_symbols.add(normalized)
        return normalized

    @staticmethod
    def normalize_symbols(symbols: Iterable[str]) -> list[str]:
        normalized = sorted(
            {str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()}
        )
        return normalized

    @staticmethod
    def build_bucket_id(symbol: str, bucket_count: int) -> int:
        return zlib.crc32(symbol.encode("utf-8")) % bucket_count

    @classmethod
    def build_bucket_map(cls, symbols: Iterable[str], bucket_count: int) -> dict[int, list[str]]:
        buckets: dict[int, list[str]] = {bucket_id: [] for bucket_id in range(bucket_count)}
        for symbol in cls.normalize_symbols(symbols):
            buckets[cls.build_bucket_id(symbol, bucket_count)].append(symbol)
        return {bucket_id: items for bucket_id, items in buckets.items() if items}
