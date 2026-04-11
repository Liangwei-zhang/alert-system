import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from domains.analytics.backtest.service import BacktestService


class FakeRepository:
    def __init__(self, window_data, *, save_rankings_error=None):
        self.window_data = window_data
        self.save_rankings_error = save_rankings_error
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
        if self.save_rankings_error is not None:
            raise self.save_rankings_error
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
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(length):
        price += 1.2
        bars.append(
            {
                "timestamp": start + timedelta(days=index),
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
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for index in range(length):
        base += deltas[index % len(deltas)]
        bars.append(
            {
                "timestamp": start + timedelta(days=index),
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

        with patch(
            "domains.analytics.backtest.service.capture_code_version",
            return_value="main@abc123def456",
        ):
            result = await service.refresh_rankings(windows=[30, 90], timeframe="1d")

        self.assertEqual(result["ranking_count"], len(result["rankings"]))
        self.assertTrue(repository.saved_runs)
        self.assertTrue(repository.saved_results)
        self.assertTrue(repository.saved_rankings)
        self.assertEqual(publisher.events[0]["topic"], "ops.audit.logged")
        self.assertEqual(result["rankings"][0]["rank"], 1)
        self.assertIn("windows", result["rankings"][0]["evidence"])
        self.assertEqual(result["experiment_name"], "backtest.ranking-refresh")
        self.assertEqual(result["code_version"], "main@abc123def456")
        self.assertTrue(result["dataset_fingerprint"])
        self.assertTrue(result["run_key"].startswith("backtest-ranking-refresh:1d:"))
        self.assertEqual(repository.saved_runs[0]["config"]["universe"]["count"], 2)
        self.assertEqual(
            repository.saved_runs[0]["config"]["strategy_names"],
            ["trend_following", "mean_reversion", "breakout"],
        )
        self.assertEqual(repository.saved_runs[0]["code_version"], "main@abc123def456")
        self.assertTrue(repository.saved_runs[0]["dataset_fingerprint"])
        self.assertEqual(repository.saved_results[0][1]["artifacts"]["entries"][0]["name"], "backtest_run")
        self.assertEqual(
            repository.saved_results[0][1]["artifacts"]["entries"][1]["name"],
            "strategy_rankings",
        )

    async def test_refresh_rankings_normalizes_benchmark_aliases(self):
        repository = FakeRepository({"AAPL": build_trending_bars()})
        service = BacktestService(
            repository=repository,
            symbol_provider=lambda: ["AAPL"],
        )

        result = await service.refresh_rankings(
            strategy_names=["buy-and-hold", "sma-cross", "rsi", "bollinger"],
            windows=[30],
        )

        self.assertEqual(
            [item["strategy_name"] for item in result["rankings"]],
            ["buy_and_hold", "sma_cross", "rsi_reversion", "bollinger_reversion"],
        )

    async def test_run_backtest_window_supports_buy_and_hold_baseline(self):
        repository = FakeRepository({"AAPL": build_trending_bars()})
        service = BacktestService(repository=repository)

        result = await service.run_backtest_window(
            symbol="AAPL", window_days=30, strategy_name="buy_and_hold"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["metrics"]["trade_count"], 1)
        self.assertGreater(result["metrics"]["total_return_percent"], 0)

    def test_compute_rsi_handles_flat_series(self):
        service = BacktestService(repository=FakeRepository({}))

        rsi = service._compute_rsi([100.0] * 15)

        self.assertEqual(rsi, 50.0)

    def test_calculate_degradation_penalizes_unstable_scores(self):
        service = BacktestService(repository=FakeRepository({}))

        degradation = service.calculate_degradation({30: 18.0, 90: 12.0, 365: 4.0})

        self.assertGreater(degradation, 0)

    async def test_refresh_rankings_marks_run_failed_when_save_rankings_errors(self):
        repository = FakeRepository(
            {"AAPL": build_trending_bars()},
            save_rankings_error=RuntimeError("rankings write failed"),
        )
        service = BacktestService(repository=repository, symbol_provider=lambda: ["AAPL"])

        with patch(
            "domains.analytics.backtest.service.capture_code_version",
            return_value="main@abc123def456",
        ):
            with self.assertRaisesRegex(RuntimeError, "rankings write failed"):
                await service.refresh_rankings(windows=[30], timeframe="1d")

        self.assertEqual(repository.saved_results[-1][1]["status"], "failed")
        self.assertEqual(
            repository.saved_results[-1][1]["error_message"],
            "rankings write failed",
        )
        self.assertEqual(repository.saved_results[-1][1]["artifacts"]["entries"][0]["name"], "backtest_run")


if __name__ == "__main__":
    unittest.main()
