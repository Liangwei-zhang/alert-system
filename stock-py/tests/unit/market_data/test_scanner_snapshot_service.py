import unittest
from datetime import datetime, timedelta, timezone

from domains.market_data.scanner_snapshot_service import ScannerSnapshotService


class ScannerSnapshotServiceTest(unittest.TestCase):
    def test_build_snapshot_returns_buy_setup_for_uptrend(self) -> None:
        service = ScannerSnapshotService()
        start = datetime(2026, 3, 1, tzinfo=timezone.utc)
        bars = []
        price = 100.0
        for index in range(25):
            price += 1.5
            bars.append(
                {
                    "timestamp": start + timedelta(days=index),
                    "open": price - 0.8,
                    "high": price + 1.0,
                    "low": price - 1.2,
                    "close": price,
                    "volume": 1000 + (index * 50),
                }
            )

        snapshot = service.build_snapshot("AAPL", bars)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["direction"], "buy")
        self.assertGreater(snapshot["confidence"], 60)
        self.assertIn("analysis", snapshot)

    def test_build_snapshot_returns_none_when_insufficient_bars(self) -> None:
        service = ScannerSnapshotService()

        snapshot = service.build_snapshot(
            "AAPL",
            [{"open": 1, "high": 2, "low": 1, "close": 1.5, "volume": 1} for _ in range(10)],
        )

        self.assertIsNone(snapshot)


if __name__ == "__main__":
    unittest.main()
