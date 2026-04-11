import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.trades.service import TradeService
from infra.db.models.trades import TradeAction, TradeStatus


class TradeServiceReadPathTest(unittest.TestCase):
    def test_get_trade_info_by_id_uses_cached_snapshot_payload(self) -> None:
        service = TradeService(SimpleNamespace(info={}))
        cached_payload = {
            "id": "trade-42",
            "user_id": 7,
            "symbol": "AAPL",
            "action": "buy",
            "suggested_shares": 10.0,
            "suggested_price": 150.0,
            "suggested_amount": 1500.0,
            "status": "pending",
            "expires_at": "2026-04-04T00:00:00+00:00",
            "link_token": "token-123",
            "link_sig": "sig-123",
        }

        with patch(
            "domains.trades.service.get_or_load_trade_snapshot",
            AsyncMock(return_value=cached_payload),
        ) as cache_loader:
            trade = asyncio.run(service.get_trade_info_by_id("trade-42"))

        cache_loader.assert_awaited_once()
        self.assertIsNotNone(trade)
        assert trade is not None
        self.assertEqual(trade.id, "trade-42")
        self.assertEqual(trade.user_id, 7)
        self.assertEqual(trade.action, TradeAction.BUY)
        self.assertEqual(trade.status, TradeStatus.PENDING)

    def test_get_trade_info_for_user_filters_other_users(self) -> None:
        service = TradeService(SimpleNamespace(info={}))

        async def fake_get_trade_info_by_id(trade_id: str):
            self.assertEqual(trade_id, "trade-42")
            return SimpleNamespace(id="trade-42", user_id=7)

        with patch.object(
            service, "get_trade_info_by_id", AsyncMock(side_effect=fake_get_trade_info_by_id)
        ):
            trade = asyncio.run(service.get_trade_info_for_user("trade-42", 8))

        self.assertIsNone(trade)

    def test_ignore_trade_schedules_trade_info_invalidation(self) -> None:
        session = SimpleNamespace(info={})
        service = TradeService(session)
        trade = SimpleNamespace(id="trade-42", user_id=7, action=TradeAction.BUY, symbol="AAPL")
        service.repo = SimpleNamespace(mark_ignored=AsyncMock(return_value=True))
        service._publish_trade_action = AsyncMock()

        with patch("domains.trades.service.schedule_invalidate_trade_info") as invalidator:
            result = asyncio.run(service.ignore_trade(trade))

        self.assertTrue(result)
        invalidator.assert_called_once_with(session, "trade-42")

    def test_acknowledge_receipts_batches_repository_and_outbox_work(self) -> None:
        service = TradeService(SimpleNamespace(info={}))
        trade = SimpleNamespace(id="trade-42", user_id=7)
        service.notification_repository = SimpleNamespace(
            list_ids_by_trade=AsyncMock(return_value=["n-2", "n-1"])
        )
        service.receipt_repository = SimpleNamespace(acknowledge_many=AsyncMock())
        service.outbox = SimpleNamespace(publish_batch_after_commit=AsyncMock())

        asyncio.run(service.acknowledge_receipts(trade))

        service.notification_repository.list_ids_by_trade.assert_awaited_once_with(7, "trade-42")
        service.receipt_repository.acknowledge_many.assert_awaited_once_with(["n-2", "n-1"], 7)
        service.outbox.publish_batch_after_commit.assert_awaited_once()
        published_events = list(service.outbox.publish_batch_after_commit.await_args.args[0])
        self.assertEqual(
            [event.key for event in published_events],
            ["n-2", "n-1"],
        )
        self.assertEqual(
            published_events[0].payload,
            {"user_id": 7, "notification_id": "n-2", "trade_id": "trade-42"},
        )

    def test_acknowledge_receipts_skips_work_without_notifications(self) -> None:
        service = TradeService(SimpleNamespace(info={}))
        trade = SimpleNamespace(id="trade-42", user_id=7)
        service.notification_repository = SimpleNamespace(
            list_ids_by_trade=AsyncMock(return_value=[])
        )
        service.receipt_repository = SimpleNamespace(acknowledge_many=AsyncMock())
        service.outbox = SimpleNamespace(publish_batch_after_commit=AsyncMock())

        asyncio.run(service.acknowledge_receipts(trade))

        service.notification_repository.list_ids_by_trade.assert_awaited_once_with(7, "trade-42")
        service.receipt_repository.acknowledge_many.assert_not_called()
        service.outbox.publish_batch_after_commit.assert_not_called()

    def test_apply_buy_to_portfolio_builds_staged_exit_metadata(self) -> None:
        service = TradeService(SimpleNamespace(info={}))
        service.portfolio_repository = SimpleNamespace(
            get_by_user_and_symbol=AsyncMock(return_value=None),
            create=AsyncMock(),
        )
        trade = SimpleNamespace(
            user_id=7,
            symbol="AAPL",
            action=TradeAction.BUY,
            extra=json.dumps(
                {
                    "take_profit_1": 120.0,
                    "take_profit_2": 128.0,
                    "take_profit_3": 140.0,
                    "stop_loss": 94.0,
                }
            ),
        )

        asyncio.run(service._apply_buy_to_portfolio(trade, shares=10, price=100.0, amount=1000.0))

        create_kwargs = service.portfolio_repository.create.await_args.kwargs
        self.assertAlmostEqual(create_kwargs["target_profit"], 0.2)
        self.assertAlmostEqual(create_kwargs["stop_loss"], 0.06)
        self.assertEqual(create_kwargs["extra"]["sell_plan"]["base_shares"], 10)
        self.assertEqual(
            [stage["id"] for stage in create_kwargs["extra"]["sell_plan"]["stages"]],
            ["tp1", "tp2", "tp3"],
        )

    def test_apply_sell_to_portfolio_marks_stage_progress(self) -> None:
        service = TradeService(SimpleNamespace(info={}))
        position = SimpleNamespace(
            shares=10,
            avg_cost=100.0,
            target_profit=0.15,
            stop_loss=0.08,
            extra=json.dumps(
                {
                    "sell_plan": {
                        "base_shares": 10,
                        "stages": [
                            {"id": "tp1", "label": "Batch 1", "trigger_pct": 0.15, "sell_pct": 0.25},
                            {"id": "tp2", "label": "Batch 2", "trigger_pct": 0.23, "sell_pct": 0.35},
                            {"id": "tp3", "label": "Batch 3", "trigger_pct": 0.35, "sell_pct": 0.4},
                        ],
                    },
                    "sell_progress": {"completed_stage_ids": []},
                }
            ),
        )
        service.portfolio_repository = SimpleNamespace(
            get_by_user_and_symbol=AsyncMock(return_value=position),
            update=AsyncMock(),
            delete=AsyncMock(),
        )
        trade = SimpleNamespace(
            user_id=7,
            symbol="AAPL",
            action=TradeAction.SELL,
            extra=json.dumps({"sell_stage_id": "tp1"}),
        )

        asyncio.run(service._apply_sell_to_portfolio(trade, shares=3, price=120.0))

        update_args = service.portfolio_repository.update.await_args.args[1]
        self.assertEqual(update_args["shares"], 7)
        updated_extra = update_args["extra"]
        self.assertEqual(updated_extra["sell_progress"]["completed_stage_ids"], ["tp1"])
        self.assertEqual(updated_extra["last_exit"]["remaining_shares"], 7)


if __name__ == "__main__":
    unittest.main()
