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
        self.assertEqual(notifications[0].title, "Buy signal: AAPL")
        self.assertEqual(notifications[0].channels, ["push", "email"])
        self.assertFalse(notifications[0].ack_required)

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
        self.assertEqual(notifications[0].title, "AI suggests sell: TSLA")
        self.assertTrue(notifications[0].ack_required)
        self.assertEqual(notifications[0].channels, ["push"])


if __name__ == "__main__":
    unittest.main()
