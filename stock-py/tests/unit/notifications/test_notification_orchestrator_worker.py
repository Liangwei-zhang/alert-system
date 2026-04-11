import unittest

from apps.workers.notification_orchestrator.worker import NotificationOrchestratorWorker


class NotificationOrchestratorWorkerTest(unittest.TestCase):
    def test_normalize_signal_generated_event(self) -> None:
        worker = NotificationOrchestratorWorker(default_channels=("push", "email"))

        notifications = worker.normalize_event(
            "signal.generated",
            {
                "user_ids": [7],
                "symbol": "aapl",
                "signal_type": "buy",
                "price": 182.4,
            },
        )

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].user_id, 7)
        self.assertEqual(notifications[0].title, "买入信号：AAPL")
        self.assertEqual(notifications[0].channels, ["push", "email"])
        self.assertFalse(notifications[0].ack_required)

    def test_normalize_notification_batch_requested_event(self) -> None:
        worker = NotificationOrchestratorWorker(default_channels=("push",))

        notifications = worker.normalize_event(
            "notification.batch.requested",
            {
                "user_ids": [12],
                "symbol": "msft",
                "signal_type": "sell",
                "price": 401.2,
            },
        )

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].user_id, 12)
        self.assertEqual(notifications[0].title, "卖出信号：MSFT")
        self.assertEqual(notifications[0].channels, ["push"])

    def test_normalize_tradingagents_terminal_event_defaults_ack(self) -> None:
        worker = NotificationOrchestratorWorker(default_channels=("push",))

        notifications = worker.normalize_event(
            "tradingagents.terminal",
            {
                "user_id": 9,
                "ticker": "tsla",
                "final_action": "sell",
                "decision_summary": "Reduce exposure into strength.",
            },
        )

        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].title, "AI 建议卖出：TSLA")
        self.assertTrue(notifications[0].ack_required)
        self.assertEqual(notifications[0].channels, ["push"])


class StubFanoutWorker(NotificationOrchestratorWorker):
    def __init__(self) -> None:
        super().__init__()
        self.fanned_out_payloads: list[dict] = []

    async def _fanout_signal_generated(self, payload: dict[str, object]) -> dict[str, int]:
        self.fanned_out_payloads.append(dict(payload))
        return {"created": 0, "requested": 0}


class NotificationOrchestratorWorkerFanoutTest(unittest.IsolatedAsyncioTestCase):
    async def test_process_event_routes_deferred_signal_to_fanout(self) -> None:
        worker = StubFanoutWorker()

        result = await worker.process_event(
            "signal.generated",
            {
                "signal_id": "1001",
                "symbol": "AAPL",
                "signal_type": "buy",
                "score": 82,
                "user_ids": [],
            },
        )

        self.assertEqual(result, {"created": 0, "requested": 0})
        self.assertEqual(len(worker.fanned_out_payloads), 1)


if __name__ == "__main__":
    unittest.main()
