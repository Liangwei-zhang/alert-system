import asyncio
import unittest
from types import SimpleNamespace

from domains.search.service import SearchService


class FakeSearchRepository:
    def __init__(self, items) -> None:
        self.items = items
        self.calls: list[dict] = []

    async def search_symbols(self, q: str, limit: int, asset_type: str | None):
        self.calls.append({"q": q, "limit": limit, "asset_type": asset_type})
        return self.items


class SearchServiceTest(unittest.TestCase):
    def test_search_symbols_normalizes_query_for_repository_and_preserves_original_query(
        self,
    ) -> None:
        repository = FakeSearchRepository(
            [
                SimpleNamespace(
                    symbol="AAPL",
                    name="Apple Inc.",
                    name_zh="蘋果",
                    asset_type="stock",
                    exchange="NASDAQ",
                    sector="Technology",
                )
            ]
        )
        service = SearchService(repository)

        response = asyncio.run(service.search_symbols(" aapl ", limit=5, asset_type="stock"))

        self.assertEqual(repository.calls, [{"q": "AAPL", "limit": 5, "asset_type": "stock"}])
        self.assertEqual(response.query, " aapl ")
        self.assertEqual(len(response.items), 1)
        self.assertEqual(response.items[0].symbol, "AAPL")
        self.assertEqual(response.items[0].exchange, "NASDAQ")

    def test_search_symbols_returns_empty_payload_when_repository_finds_nothing(self) -> None:
        repository = FakeSearchRepository([])

        response = asyncio.run(SearchService(repository).search_symbols("msft"))

        self.assertEqual(response.items, [])
        self.assertEqual(response.query, "msft")


if __name__ == "__main__":
    unittest.main()
