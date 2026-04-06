import unittest

from apps.workers.market_data.worker import MarketDataWorker


class StubMarketDataWorker(MarketDataWorker):
    def __init__(self) -> None:
        super().__init__(sync_queries=("AAPL",), timeframes=("1d",))
        self.calls = []

    async def sync_symbols(self, *, sync_queries=None):
        self.calls.append(("sync", tuple(sync_queries or self.sync_queries)))
        return {"synced": 3}

    async def import_ohlcv(self, *, symbols=None):
        self.calls.append(("import", tuple(symbols or [])))
        return {"imported": 12, "anomalies": 1}

    async def run_quality_checks(self, *, symbols=None):
        self.calls.append(("quality", tuple(symbols or [])))
        return {"validated": 20, "anomalies": 2}


class MarketDataWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_once_aggregates_stage_stats(self) -> None:
        worker = StubMarketDataWorker()

        result = await worker.run_once(symbols=["AAPL", "MSFT"])

        self.assertEqual(result, {"synced": 3, "imported": 12, "anomalies": 3, "validated": 20})
        self.assertEqual([call[0] for call in worker.calls], ["sync", "import", "quality"])


if __name__ == "__main__":
    unittest.main()
