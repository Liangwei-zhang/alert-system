from __future__ import annotations

import inspect
from typing import Any, Iterable


class SymbolSyncService:
    def __init__(
        self, session: Any, *, repository: Any | None = None, source_loader: Any | None = None
    ) -> None:
        self.session = session
        self.repository = repository
        self.source_loader = source_loader

    async def sync_symbols(
        self,
        *,
        query: str | None = None,
        items: Iterable[Any] | None = None,
        source: str = "yahoo",
    ) -> dict[str, Any]:
        raw_items = (
            list(items) if items is not None else await self._load_items(query=query, source=source)
        )
        normalized = [self._normalize_item(item) for item in raw_items]
        normalized = [item for item in normalized if item is not None]

        repository = self.repository or self._build_repository()
        saved = await repository.bulk_upsert_symbols(normalized)
        return {
            "query": query,
            "source": source,
            "synced_count": len(saved),
            "symbols": [record.symbol for record in saved],
        }

    async def _load_items(self, *, query: str | None, source: str) -> list[Any]:
        if self.source_loader is not None:
            result = self.source_loader(query, source)
            if inspect.isawaitable(result):
                return list(await result)
            return list(result)
        if not query:
            return []
        from infra.market_data.data_source import MarketDataSourceFactory

        return list(await MarketDataSourceFactory.search(query, source=source))

    def _build_repository(self) -> Any:
        from domains.market_data.repository import SymbolRepository

        return SymbolRepository(self.session)

    @staticmethod
    def _normalize_item(item: Any) -> dict[str, Any] | None:
        symbol = (
            str(getattr(item, "symbol", None) or item.get("symbol", "")).strip().upper()
            if isinstance(item, dict)
            else str(getattr(item, "symbol", "")).strip().upper()
        )
        if not symbol:
            return None
        get = (
            item.get
            if isinstance(item, dict)
            else lambda key, default=None: getattr(item, key, default)
        )
        asset_type = str(get("asset_type") or get("type") or "stock").lower()
        return {
            "symbol": symbol,
            "name": get("name") or symbol,
            "exchange": get("exchange") or "UNKNOWN",
            "asset_type": asset_type,
            "sector": get("sector"),
            "is_active": True,
        }
