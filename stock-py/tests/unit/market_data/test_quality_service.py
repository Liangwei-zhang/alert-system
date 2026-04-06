import unittest
from datetime import datetime, timedelta, timezone

from domains.market_data.quality_service import OhlcvQualityService


class OhlcvQualityServiceTest(unittest.TestCase):
    def test_validate_batch_flags_duplicates_and_missing_gap(self) -> None:
        service = OhlcvQualityService()
        start = datetime(2026, 4, 1, tzinfo=timezone.utc)
        bars = [
            {
                "timestamp": start,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 1000,
            },
            {
                "timestamp": start,
                "open": 100.5,
                "high": 102,
                "low": 100,
                "close": 101.5,
                "volume": 1200,
            },
            {
                "timestamp": start + timedelta(days=5),
                "open": 102,
                "high": 103,
                "low": 101,
                "close": 102.5,
                "volume": 1300,
            },
        ]

        report = service.validate_batch("AAPL", "1d", bars)

        self.assertEqual(report["stats"]["valid_count"], 2)
        self.assertEqual(report["stats"]["anomaly_count"], 2)
        codes = {item["code"] for item in report["anomalies"]}
        self.assertIn("duplicate_bar", codes)
        self.assertIn("missing_bar_gap", codes)

    def test_validate_batch_rejects_invalid_values(self) -> None:
        service = OhlcvQualityService()

        report = service.validate_batch(
            "TSLA",
            "1d",
            [
                {
                    "timestamp": "2026-04-01T00:00:00Z",
                    "open": 10,
                    "high": 9,
                    "low": 8,
                    "close": 9,
                    "volume": 100,
                }
            ],
        )

        self.assertEqual(report["stats"]["valid_count"], 0)
        self.assertEqual(report["anomalies"][0]["code"], "invalid_row")


if __name__ == "__main__":
    unittest.main()
