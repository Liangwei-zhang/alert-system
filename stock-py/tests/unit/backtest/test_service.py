import unittest
from types import SimpleNamespace

from domains.analytics.backtest.service import BacktestService


class FakeRepository:
    def __init__(self, window_data):
        self.window_data = window_data
        self.saved_runs = []
        self.saved_results = []
        self.saved_rankings = []

    async def save_run(self, payload):
        self.saved_runs.append(payload)
        return SimpleNamespace(id=len(self.saved_runs), **payload)

    async def save_results(self, run, results):
        self.saved_results.append((run, results))
        return run

    async def save_rankings(self, rankings, as_of_date=None):
        self.saved_rankings.append((rankings, as_of_date))
        return rankings

    async def load_window_data(self, symbol, window_days, timeframe="1d"):
        del window_days, timeframe
        return list(self.window_data.get(symbol, []))


class FakePublisher:
    def __init__(self):
        self.events = []

    async def publish_after_commit(self, topic, payload, key=None, headers=None):
        del headers
        self.events.append({"topic": topic, "payload": payload, "key": key})
        return self.events[-1]


def build_trending_bars(length=80):
    bars = []
    price = 100.0
    for index in range(length):
        price += 1.2
        bars.append(
            {
                "open": price - 0.6,
                "high": price + 0.9,
                "low": price - 1.1,
                "close": price,
                "volume": 1000 + (index * 30),
            }
        )
    return bars


def build_choppy_bars(length=80):
    bars = []
    base = 100.0
    deltas = [2.0, -1.5, 1.8, -1.2, 1.1, -1.8]
    for index in range(length):
        base += deltas[index % len(deltas)]
        bars.append(
            {
                "open": base - 0.5,
                "high": base + 1.0,
                "low": base - 1.0,
                "close": base,
                "volume": 900 + ((index % 5) * 40),
            }
        )
    return bars


class BacktestServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_run_backtest_window_returns_metrics(self):
        repository = FakeRepository({"AAPL": build_trending_bars()})
        service = BacktestService(repository=repository)

        result = await service.run_backtest_window(
            symbol="AAPL", window_days=30, strategy_name="trend_following"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["symbol"], "AAPL")
        self.assertGreaterEqual(result["metrics"]["trade_count"], 1)
        self.assertGreater(result["metrics"]["total_return_percent"], 0)

    async def test_refresh_rankings_builds_ranked_output_and_emits_audit(self):
        repository = FakeRepository({"AAPL": build_trending_bars(), "MSFT": build_choppy_bars()})
        publisher = FakePublisher()
        service = BacktestService(
            repository=repository,
            publisher=publisher,
            symbol_provider=lambda: ["AAPL", "MSFT"],
        )

        result = await service.refresh_rankings(windows=[30, 90], timeframe="1d")

        self.assertEqual(result["ranking_count"], len(result["rankings"]))
        self.assertTrue(repository.saved_runs)
        self.assertTrue(repository.saved_results)
        self.assertTrue(repository.saved_rankings)
        self.assertEqual(publisher.events[0]["topic"], "ops.audit.logged")
        self.assertEqual(result["rankings"][0]["rank"], 1)
        self.assertIn("windows", result["rankings"][0]["evidence"])

    def test_calculate_degradation_penalizes_unstable_scores(self):
        service = BacktestService(repository=FakeRepository({}))

        degradation = service.calculate_degradation({30: 18.0, 90: 12.0, 365: 4.0})

        self.assertGreater(degradation, 0)


if __name__ == "__main__":
    unittest.main()
