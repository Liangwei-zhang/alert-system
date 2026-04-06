import unittest

from domains.market_data.ohlcv_import_service import OhlcvImportService


class FakeRepository:
    def __init__(self) -> None:
        self.quarantined = []
        self.saved = []

    async def quarantine_bad_rows(self, symbol, timeframe, anomalies, source=None):
        self.quarantined.append((symbol, timeframe, anomalies, source))
        return anomalies

    async def bulk_upsert_bars(self, symbol, timeframe, rows, source=None):
        self.saved.append((symbol, timeframe, rows, source))
        return [{"id": index + 1} for index, _ in enumerate(rows)]


class FakePublisher:
    def __init__(self) -> None:
        self.events = []

    async def publish_after_commit(self, topic, payload, key=None, headers=None):
        del headers
        self.events.append({"topic": topic, "payload": payload, "key": key})
        return self.events[-1]


class OhlcvImportServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_import_batch_quarantines_bad_rows_and_emits_events(self) -> None:
        repository = FakeRepository()
        publisher = FakePublisher()
        service = OhlcvImportService(object(), repository=repository, publisher=publisher)

        result = await service.import_batch(
            "AAPL",
            "1d",
            [
                {
                    "date": "2026-04-01T00:00:00Z",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100.5,
                    "volume": 1000,
                },
                {
                    "date": "2026-04-01T00:00:00Z",
                    "open": 100,
                    "high": 101,
                    "low": 99,
                    "close": 100.5,
                    "volume": 1000,
                },
                {
                    "date": "2026-04-02T00:00:00Z",
                    "open": "bad",
                    "high": 103,
                    "low": 99,
                    "close": 102,
                    "volume": 1100,
                },
            ],
        )

        self.assertEqual(result["imported_count"], 1)
        self.assertEqual(result["anomaly_count"], 2)
        self.assertEqual(len(repository.quarantined), 1)
        self.assertEqual(len(repository.saved), 1)
        self.assertEqual(
            [event["topic"] for event in publisher.events],
            ["marketdata.ohlcv.imported", "ops.audit.logged"],
        )

    async def test_normalize_bar_accepts_epoch_timestamp(self) -> None:
        service = OhlcvImportService(
            object(), repository=FakeRepository(), publisher=FakePublisher()
        )

        row = service.normalize_bar(
            {
                "timestamp": 1712188800,
                "open": 10,
                "high": 12,
                "low": 9,
                "close": 11,
                "volume": 1500,
            },
            "tsla",
            "1d",
        )

        self.assertEqual(row["symbol"], "TSLA")
        self.assertEqual(row["timeframe"], "1d")
        self.assertEqual(row["close"], 11.0)


if __name__ == "__main__":
    unittest.main()
