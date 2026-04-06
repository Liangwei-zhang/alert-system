import unittest

from domains.signals.active_symbols_service import ActiveSymbolsService


class ActiveSymbolsServiceTest(unittest.TestCase):
    def test_normalize_symbols_deduplicates_and_upcases(self) -> None:
        normalized = ActiveSymbolsService.normalize_symbols([" aapl ", "AAPL", "msft", ""])

        self.assertEqual(normalized, ["AAPL", "MSFT"])

    def test_build_bucket_map_is_stable(self) -> None:
        first = ActiveSymbolsService.build_bucket_map(["AAPL", "MSFT", "TSLA"], bucket_count=8)
        second = ActiveSymbolsService.build_bucket_map(["TSLA", "MSFT", "AAPL"], bucket_count=8)

        self.assertEqual(first, second)
        self.assertTrue(all(0 <= bucket_id < 8 for bucket_id in first))

    def test_mark_symbol_dirty_normalizes_symbol(self) -> None:
        service = ActiveSymbolsService(session=None)

        symbol = service.mark_symbol_dirty(" nvda ")

        self.assertEqual(symbol, "NVDA")


if __name__ == "__main__":
    unittest.main()
