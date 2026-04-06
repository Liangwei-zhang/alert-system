import unittest

from domains.admin.runtime_metrics_service import RuntimeOperationalMetricsService


class FakeReceiptRepository:
    async def count_admin_receipts(
        self,
        *,
        follow_up_status=None,
        delivery_status=None,
        ack_required=None,
        overdue_only=False,
        user_id=None,
        notification_id=None,
    ) -> int:
        del user_id, notification_id
        if overdue_only and ack_required is True:
            return 3
        if follow_up_status == "pending":
            return 2
        if follow_up_status == "claimed":
            return 1
        if delivery_status == "delivered":
            return 11
        if delivery_status == "failed":
            return 4
        return 0


class FakeOutboxRepository:
    async def count_admin_messages(
        self, *, channel=None, status=None, user_id=None, notification_id=None
    ):
        del user_id, notification_id
        counts = {
            (None, "pending"): 7,
            (None, "processing"): 2,
            (None, "failed"): 1,
            ("email", "pending"): 4,
            ("email", "processing"): 1,
            ("email", "failed"): 1,
            ("push", "pending"): 3,
            ("push", "processing"): 1,
            ("push", "failed"): 0,
        }
        return counts[(channel, status)]


class FakeEventOutboxRepository:
    async def count_runtime_records(self, *, status=None, retried_only=False) -> int:
        if retried_only:
            return 2
        if status == "pending":
            return 6
        if status == "published":
            return 19
        return 0


class FakeTradeRepository:
    async def count_claimable_trades(self) -> int:
        return 5

    async def count_expirable_trades(self) -> int:
        return 2

    async def get_claim_latency_stats(self, *, since, limit):
        del since, limit
        return {"count": 4, "avg_seconds": 37.25, "max_seconds": 91.0}


class RuntimeOperationalMetricsServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_collect_metric_points_emits_backlog_and_latency_metrics(self) -> None:
        service = RuntimeOperationalMetricsService(
            object(),
            receipt_repository=FakeReceiptRepository(),
            outbox_repository=FakeOutboxRepository(),
            event_outbox_repository=FakeEventOutboxRepository(),
            trade_repository=FakeTradeRepository(),
        )

        metrics = await service.collect_metric_points()

        metric_index = {
            (metric.name, tuple(sorted(metric.labels.items()))): metric.value for metric in metrics
        }
        self.assertEqual(
            metric_index[("notification_outbox_messages_total", (("status", "pending"),))],
            7.0,
        )
        self.assertEqual(
            metric_index[
                (
                    "notification_outbox_channel_messages_total",
                    (("channel", "email"), ("status", "pending")),
                )
            ],
            4.0,
        )
        self.assertEqual(
            metric_index[("notification_receipts_total", (("state", "overdue"),))],
            3.0,
        )
        self.assertEqual(metric_index[("event_outbox_retried_total", ())], 2.0)
        self.assertEqual(metric_index[("trade_claim_latency_samples_total", ())], 4.0)
        self.assertEqual(metric_index[("trade_claim_latency_seconds_avg", ())], 37.25)
        self.assertEqual(metric_index[("trade_claim_latency_seconds_max", ())], 91.0)


if __name__ == "__main__":
    unittest.main()
