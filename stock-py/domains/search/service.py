from __future__ import annotations

from domains.search.repository import SearchRepository
from domains.search.schemas import SearchSymbolItem, SearchSymbolsResponse


class SearchService:
    def __init__(self, repository: SearchRepository) -> None:
        self.repository = repository

    async def search_symbols(
        self, q: str, limit: int = 20, asset_type: str | None = None
    ) -> SearchSymbolsResponse:
        normalized_q = q.strip().upper()
        items = await self.repository.search_symbols(normalized_q, limit, asset_type)
        return SearchSymbolsResponse(
            items=[
                SearchSymbolItem(
                    symbol=item.symbol,
                    name=item.name,
                    name_zh=item.name_zh,
                    asset_type=item.asset_type,
                    exchange=item.exchange,
                    sector=item.sector,
                )
                for item in items
            ],
            query=q,
        )
