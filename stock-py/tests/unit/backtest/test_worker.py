import unittest

from apps.workers.backtest.worker import BacktestWorker


class StubBacktestWorker(BacktestWorker):
    def __init__(self):
        super().__init__(windows=(30, 90))
        self.calls = []

    async def open_session(self):
        return object()

    async def close_session(self, session):
        del session
        self.calls.append("close")

    async def commit_session(self, session):
        del session
        self.calls.append("commit")

    def build_service(self, session):
        del session
        worker = self

        class Service:
            async def refresh_rankings(self, **kwargs):
                worker.calls.append(("refresh", kwargs))
                return {
                    "run_id": 7,
                    "experiment_name": "scheduler.backtest-refresh",
                    "run_key": "scheduler-backtest-refresh:1d:20260409T120000Z",
                    "dataset_fingerprint": "abc123",
                    "code_version": "main@abc123",
                    "ranking_count": 2,
                    "rankings": [{"strategy_name": "trend_following"}],
                }

        return Service()


class BacktestWorkerTest(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_rankings_calls_service_and_commit(self):
        worker = StubBacktestWorker()

        result = await worker.refresh_rankings(symbols=["AAPL"], strategy_names=["trend_following"])

        self.assertEqual(result["ranking_count"], 2)
        self.assertEqual(worker.calls[0][0], "refresh")
        self.assertEqual(worker.calls[0][1]["experiment_name"], "scheduler.backtest-refresh")
        self.assertEqual(worker.calls[0][1]["experiment_context"]["trigger"], "scheduler")
        self.assertEqual(
            worker.calls[0][1]["experiment_context"]["dataset"]["selection_mode"],
            "active_symbols",
        )
        self.assertEqual(worker.calls[1], "commit")
        self.assertEqual(worker.calls[2], "close")


if __name__ == "__main__":
    unittest.main()
