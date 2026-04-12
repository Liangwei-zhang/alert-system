from __future__ import annotations

import unittest
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from apps.public_api import main as public_main
from apps.public_api.routers import chart_data


class _FakeMarketDataProxyService:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    async def get_historical(self, *, source: str, symbol: str, period: str = "1mo") -> dict:
        self.calls.append({"source": source, "symbol": symbol, "period": period})
        return {
            "source": source,
            "symbol": symbol,
            "period": period,
            "bars": [
                {
                    "date": datetime(2026, 4, 9, tzinfo=timezone.utc),
                    "open": 100.0,
                    "high": 105.0,
                    "low": 99.0,
                    "close": 104.0,
                    "volume": 1200,
                },
                {
                    "date": datetime(2026, 4, 10, tzinfo=timezone.utc),
                    "open": 104.0,
                    "high": 109.0,
                    "low": 103.0,
                    "close": 108.0,
                    "volume": 1800,
                },
            ],
        }


class PublicMarketChartRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(public_main.app)
        self.fake_service = _FakeMarketDataProxyService()
        public_main.app.dependency_overrides[chart_data._market_data_service] = lambda: self.fake_service

    def tearDown(self) -> None:
        self.client.close()
        public_main.app.dependency_overrides.clear()

    def test_market_chart_route_builds_quote_summary_for_equity_symbol(self) -> None:
        response = self.client.get("/v1/market/chart/AAPL?period=3mo")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["symbol"], "AAPL")
        self.assertEqual(payload["source"], "yahoo")
        self.assertEqual(payload["period"], "3mo")
        self.assertEqual(len(payload["bars"]), 2)
        self.assertEqual(payload["quote"]["latest_close"], 108.0)
        self.assertEqual(payload["quote"]["previous_close"], 104.0)
        self.assertEqual(payload["quote"]["change"], 4.0)
        self.assertAlmostEqual(payload["quote"]["change_pct"], 3.8461538461, places=6)
        self.assertEqual(self.fake_service.calls[-1], {"source": "yahoo", "symbol": "AAPL", "period": "3mo"})

    def test_market_chart_route_auto_uses_binance_for_crypto_symbol(self) -> None:
        response = self.client.get("/v1/market/chart/BTCUSDT?asset_type=crypto&period=6mo")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "binance")
        self.assertEqual(payload["asset_type"], "crypto")
        self.assertEqual(self.fake_service.calls[-1], {"source": "binance", "symbol": "BTCUSDT", "period": "6mo"})


if __name__ == "__main__":
    unittest.main()