from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routers import runtime_monitoring as runtime_router
from apps.admin_api.routers import tasks as tasks_router
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session
from infra.http.health import router as health_router


class EnumValue:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeReceiptRepository:
    list_records = []
    overdue_records = []
    records_by_id = {}
    total = 0
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.list_records = []
        cls.overdue_records = []
        cls.records_by_id = {}
        cls.total = 0
        cls.calls = {
            "list_admin_receipts": [],
            "count_admin_receipts": [],
            "list_overdue_receipts": [],
            "get_by_id": [],
            "acknowledge": [],
            "mark_manual_follow_up_pending": [],
            "claim_manual_follow_up": [],
            "resolve_follow_up": [],
        }

    @classmethod
    def _find_by_notification(cls, notification_id: str, user_id: int):
        for receipt in cls.records_by_id.values():
            if str(receipt.notification_id) == notification_id and int(receipt.user_id) == user_id:
                return receipt
        return None

    async def list_admin_receipts(self, **kwargs):
        self.calls["list_admin_receipts"].append(kwargs)
        return list(self.list_records)

    async def count_admin_receipts(self, **kwargs) -> int:
        self.calls["count_admin_receipts"].append(kwargs)
        return self.total

    async def list_overdue_receipts(self, limit: int = 100):
        self.calls["list_overdue_receipts"].append(limit)
        return list(self.overdue_records[:limit])

    async def get_by_id(self, receipt_id: str):
        self.calls["get_by_id"].append(receipt_id)
        return self.records_by_id.get(receipt_id)

    async def acknowledge(self, notification_id: str, user_id: int):
        self.calls["acknowledge"].append({"notification_id": notification_id, "user_id": user_id})
        receipt = self._find_by_notification(notification_id, user_id)
        if receipt is None:
            return None
        timestamp = datetime(2026, 4, 5, 0, 5, tzinfo=timezone.utc)
        receipt.opened_at = receipt.opened_at or timestamp
        receipt.acknowledged_at = timestamp
        receipt.manual_follow_up_status = "resolved"
        receipt.manual_follow_up_updated_at = timestamp
        receipt.updated_at = timestamp
        return receipt

    async def mark_manual_follow_up_pending(self, receipt_id: str, escalation_level: int):
        self.calls["mark_manual_follow_up_pending"].append(
            {"receipt_id": receipt_id, "escalation_level": escalation_level}
        )
        receipt = self.records_by_id.get(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "pending"
        receipt.escalation_level = escalation_level
        receipt.manual_follow_up_updated_at = datetime.now(timezone.utc)
        return receipt

    async def claim_manual_follow_up(self, receipt_id: str):
        self.calls["claim_manual_follow_up"].append(receipt_id)
        receipt = self.records_by_id.get(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "claimed"
        receipt.updated_at = datetime.now(timezone.utc)
        receipt.manual_follow_up_updated_at = receipt.updated_at
        return receipt

    async def resolve_follow_up(self, receipt_id: str):
        self.calls["resolve_follow_up"].append(receipt_id)
        receipt = self.records_by_id.get(receipt_id)
        if receipt is None:
            return None
        receipt.manual_follow_up_status = "resolved"
        receipt.updated_at = datetime.now(timezone.utc)
        receipt.manual_follow_up_updated_at = receipt.updated_at
        return receipt


class FakeOutboxRepository:
    list_records = []
    records_by_id = {}
    total = 0
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.list_records = []
        cls.records_by_id = {}
        cls.total = 0
        cls.calls = {
            "list_admin_messages": [],
            "count_admin_messages": [],
            "claim_pending": [],
            "get_by_id": [],
            "requeue": [],
            "release_stale_processing": [],
        }

    @classmethod
    def _filtered_records(
        cls,
        *,
        channel: str | None = None,
        status: str | None = None,
        user_id: int | None = None,
        notification_id: str | None = None,
    ):
        items = list(cls.list_records)
        if channel:
            items = [item for item in items if str(item.channel) == channel]
        if status:
            items = [item for item in items if str(item.status) == status]
        if user_id is not None:
            items = [item for item in items if int(item.user_id) == user_id]
        if notification_id:
            items = [
                item
                for item in items
                if str(getattr(item, "notification_id", None) or "") == notification_id
            ]
        return items

    async def list_admin_messages(self, **kwargs):
        self.calls["list_admin_messages"].append(kwargs)
        items = self._filtered_records(
            channel=kwargs.get("channel"),
            status=kwargs.get("status"),
            user_id=kwargs.get("user_id"),
            notification_id=kwargs.get("notification_id"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_admin_messages(self, **kwargs) -> int:
        self.calls["count_admin_messages"].append(kwargs)
        return len(
            self._filtered_records(
                channel=kwargs.get("channel"),
                status=kwargs.get("status"),
                user_id=kwargs.get("user_id"),
                notification_id=kwargs.get("notification_id"),
            )
        )

    async def claim_pending(self, channel: str, limit: int = 100):
        self.calls["claim_pending"].append({"channel": channel, "limit": limit})
        claimed = []
        for message in self._filtered_records(channel=channel, status="pending")[:limit]:
            message.status = "processing"
            payload = dict(message.payload or {})
            payload["_claimed_at"] = "2026-04-05T00:05:00+00:00"
            message.payload = payload
            claimed.append(message)
        return claimed

    async def get_by_id(self, outbox_id: str):
        self.calls["get_by_id"].append(outbox_id)
        return self.records_by_id.get(outbox_id)

    async def requeue(self, outbox_id: str):
        self.calls["requeue"].append(outbox_id)
        message = self.records_by_id.get(outbox_id)
        if message is None:
            return None
        message.status = "pending"
        payload = dict(message.payload or {})
        payload.pop("_last_error", None)
        payload.pop("_claimed_at", None)
        message.payload = payload
        return message

    async def release_stale_processing(
        self,
        *,
        channel: str | None = None,
        older_than_minutes: int = 15,
        limit: int = 100,
    ):
        self.calls["release_stale_processing"].append(
            {
                "channel": channel,
                "older_than_minutes": older_than_minutes,
                "limit": limit,
            }
        )
        released = []
        for message in self._filtered_records(channel=channel, status="processing")[:limit]:
            message.status = "pending"
            payload = dict(message.payload or {})
            payload.pop("_claimed_at", None)
            message.payload = payload
            released.append(message)
        return released


class FakeTradeRepository:
    list_records = []
    expirable_records = []
    claimable_records = []
    records_by_id = {}
    total = 0
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.list_records = []
        cls.expirable_records = []
        cls.claimable_records = []
        cls.records_by_id = {}
        cls.total = 0
        cls.calls = {
            "list_admin_trades": [],
            "count_admin_trades": [],
            "list_expirable_trades": [],
            "list_claimable_trades": [],
            "get_by_id": [],
            "claim": [],
            "mark_expired": [],
        }

    @classmethod
    def _filtered_records(
        cls,
        *,
        status: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        symbol: str | None = None,
        expired_only: bool = False,
        claimed_only: bool = False,
        claimed_by_operator_id: int | None = None,
    ):
        items = list(cls.list_records)
        if status:
            items = [
                item for item in items if str(getattr(item.status, "value", item.status)) == status
            ]
        if action:
            items = [
                item for item in items if str(getattr(item.action, "value", item.action)) == action
            ]
        if user_id is not None:
            items = [item for item in items if int(item.user_id) == user_id]
        if symbol:
            items = [item for item in items if str(item.symbol) == symbol.upper()]
        if expired_only:
            items = [item for item in items if bool(getattr(item, "is_expired_hint", False))]
        if claimed_only:
            items = [
                item for item in items if getattr(item, "claimed_by_operator_id", None) is not None
            ]
        if claimed_by_operator_id is not None:
            items = [
                item
                for item in items
                if getattr(item, "claimed_by_operator_id", None) == claimed_by_operator_id
            ]
        return items

    async def list_admin_trades(self, **kwargs):
        self.calls["list_admin_trades"].append(kwargs)
        items = self._filtered_records(
            status=kwargs.get("status"),
            action=kwargs.get("action"),
            user_id=kwargs.get("user_id"),
            symbol=kwargs.get("symbol"),
            expired_only=kwargs.get("expired_only", False),
            claimed_only=kwargs.get("claimed_only", False),
            claimed_by_operator_id=kwargs.get("claimed_by_operator_id"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_admin_trades(self, **kwargs) -> int:
        self.calls["count_admin_trades"].append(kwargs)
        return len(
            self._filtered_records(
                status=kwargs.get("status"),
                action=kwargs.get("action"),
                user_id=kwargs.get("user_id"),
                symbol=kwargs.get("symbol"),
                expired_only=kwargs.get("expired_only", False),
                claimed_only=kwargs.get("claimed_only", False),
                claimed_by_operator_id=kwargs.get("claimed_by_operator_id"),
            )
        )

    async def list_expirable_trades(
        self, *, limit: int = 100, user_id: int | None = None, symbol: str | None = None
    ):
        self.calls["list_expirable_trades"].append(
            {"limit": limit, "user_id": user_id, "symbol": symbol}
        )
        items = list(self.expirable_records)
        if user_id is not None:
            items = [item for item in items if int(item.user_id) == user_id]
        if symbol is not None:
            items = [item for item in items if str(item.symbol) == symbol.upper()]
        return list(items[:limit])

    async def list_claimable_trades(
        self, *, limit: int = 100, user_id: int | None = None, symbol: str | None = None
    ):
        self.calls["list_claimable_trades"].append(
            {"limit": limit, "user_id": user_id, "symbol": symbol}
        )
        items = list(self.claimable_records)
        if user_id is not None:
            items = [item for item in items if int(item.user_id) == user_id]
        if symbol is not None:
            items = [item for item in items if str(item.symbol) == symbol.upper()]
        return list(items[:limit])

    async def get_by_id(self, trade_id: str):
        self.calls["get_by_id"].append(trade_id)
        return self.records_by_id.get(trade_id)

    async def claim(self, trade_id: str, operator_user_id: int):
        self.calls["claim"].append({"trade_id": trade_id, "operator_user_id": operator_user_id})
        trade = self.records_by_id.get(trade_id)
        if trade is None:
            return None
        if str(getattr(trade.status, "value", trade.status)) != "pending":
            return None
        if bool(getattr(trade, "is_expired_hint", False)):
            return None
        if getattr(trade, "claimed_by_operator_id", None) is not None:
            return None
        trade.claimed_by_operator_id = operator_user_id
        trade.claimed_at = datetime(2026, 4, 5, 0, 15, tzinfo=timezone.utc)
        trade.updated_at = trade.claimed_at
        return trade

    async def mark_expired(self, trade_id: str):
        self.calls["mark_expired"].append(trade_id)
        trade = self.records_by_id.get(trade_id)
        if trade is None:
            return None
        if str(getattr(trade.status, "value", trade.status)) != "pending":
            return None
        if not bool(getattr(trade, "is_expired_hint", False)):
            return None
        trade.status = EnumValue("expired")
        trade.updated_at = datetime(2026, 4, 5, 0, 20, tzinfo=timezone.utc)
        trade.is_expired_hint = True
        return trade


class FakeOperatorRepository:
    operators_by_user_id = {}
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.operators_by_user_id = {}
        cls.calls = {"get_active_operator": [], "touch_operator": []}

    async def get_active_operator(self, user_id: int, *, allowed_roles: set[str] | None = None):
        self.calls["get_active_operator"].append(
            {"user_id": user_id, "allowed_roles": allowed_roles}
        )
        operator = self.operators_by_user_id.get(user_id)
        if operator is None or not bool(operator.is_active):
            return None, None
        role = str(getattr(operator.role, "value", operator.role))
        if allowed_roles is not None and role not in allowed_roles:
            return None, None
        user = SimpleNamespace(
            id=user_id,
            email=f"operator-{user_id}@example.com",
            name=f"Operator {user_id}",
        )
        return operator, user

    async def touch_operator(self, user_id: int):
        self.calls["touch_operator"].append(user_id)
        operator = self.operators_by_user_id.get(user_id)
        if operator is None:
            return None
        operator.last_action_at = datetime(2026, 4, 5, 0, 16, tzinfo=timezone.utc)
        return operator


class FakeOutboxPublisher:
    events: list[dict] = []

    def __init__(self, session) -> None:
        self.session = session

    @classmethod
    def reset(cls) -> None:
        cls.events = []

    async def publish_after_commit(
        self,
        topic: str,
        payload: dict,
        key: str | None = None,
        headers: dict | None = None,
    ):
        self.events.append(
            {"topic": topic, "payload": dict(payload), "key": key, "headers": dict(headers or {})}
        )
        return SimpleNamespace(topic=topic, payload=payload, key=key, headers=headers or {})


class AdminTasksAndRuntimeRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeReceiptRepository.reset()
        FakeOutboxRepository.reset()
        FakeTradeRepository.reset()
        FakeOperatorRepository.reset()
        FakeOutboxPublisher.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(health_router)
        self.app.include_router(tasks_router.router)
        self.app.include_router(runtime_router.router)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session

        self.receipt_repository_patch = patch.object(
            tasks_router,
            "ReceiptRepository",
            FakeReceiptRepository,
        )
        self.outbox_repository_patch = patch.object(
            tasks_router,
            "MessageOutboxRepository",
            FakeOutboxRepository,
        )
        self.trade_repository_patch = patch.object(
            tasks_router,
            "TradeRepository",
            FakeTradeRepository,
        )
        self.operator_repository_patch = patch.object(
            tasks_router,
            "OperatorRepository",
            FakeOperatorRepository,
        )
        self.outbox_publisher_patch = patch.object(
            tasks_router,
            "OutboxPublisher",
            FakeOutboxPublisher,
        )
        self.receipt_repository_patch.start()
        self.outbox_repository_patch.start()
        self.trade_repository_patch.start()
        self.operator_repository_patch.start()
        self.outbox_publisher_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.receipt_repository_patch.stop()
        self.outbox_repository_patch.stop()
        self.trade_repository_patch.stop()
        self.operator_repository_patch.stop()
        self.outbox_publisher_patch.stop()

    def test_tasks_routes_list_and_execute_actions(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        overdue_receipt = SimpleNamespace(
            id="receipt-1",
            notification_id="notification-1",
            user_id=42,
            ack_required=True,
            ack_deadline_at=now - timedelta(minutes=15),
            opened_at=None,
            acknowledged_at=None,
            last_delivery_channel="push",
            last_delivery_status="failed",
            escalation_level=1,
            manual_follow_up_status="pending",
            manual_follow_up_updated_at=now - timedelta(minutes=10),
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=20),
        )
        outbox_message = SimpleNamespace(
            id="outbox-1",
            notification_id="notification-1",
            user_id=42,
            channel="email",
            status="failed",
            payload={"subject": "Action required", "_last_error": "smtp_timeout"},
            created_at=now - timedelta(minutes=45),
        )
        pending_email_message = SimpleNamespace(
            id="outbox-2",
            notification_id="notification-2",
            user_id=42,
            channel="email",
            status="pending",
            payload={"subject": "Digest"},
            created_at=now - timedelta(minutes=30),
        )
        stale_processing_message = SimpleNamespace(
            id="outbox-3",
            notification_id="notification-3",
            user_id=42,
            channel="email",
            status="processing",
            payload={"subject": "Follow up", "_claimed_at": "2026-04-04T22:30:00+00:00"},
            created_at=now - timedelta(hours=2),
        )
        failed_push_message = SimpleNamespace(
            id="outbox-4",
            notification_id="notification-4",
            user_id=77,
            channel="push",
            status="failed",
            payload={"title": "Push fallback", "_last_error": "push_timeout"},
            created_at=now - timedelta(minutes=20),
        )
        expired_trade = SimpleNamespace(
            id="trade-1",
            user_id=42,
            symbol="AAPL",
            action=EnumValue("buy"),
            status=EnumValue("pending"),
            suggested_shares=5.0,
            suggested_price=190.25,
            suggested_amount=951.25,
            actual_shares=None,
            actual_price=None,
            actual_amount=None,
            expires_at=now - timedelta(minutes=5),
            confirmed_at=None,
            created_at=now - timedelta(hours=2),
            updated_at=now - timedelta(minutes=30),
            is_expired_hint=True,
        )
        active_trade = SimpleNamespace(
            id="trade-2",
            user_id=42,
            symbol="MSFT",
            action=EnumValue("sell"),
            status=EnumValue("pending"),
            suggested_shares=3.0,
            suggested_price=420.0,
            suggested_amount=1260.0,
            actual_shares=None,
            actual_price=None,
            actual_amount=None,
            expires_at=now + timedelta(days=30),
            confirmed_at=None,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(minutes=10),
            claimed_by_operator_id=None,
            claimed_at=None,
            is_expired_hint=False,
        )

        FakeReceiptRepository.list_records = [overdue_receipt]
        FakeReceiptRepository.overdue_records = [overdue_receipt]
        FakeReceiptRepository.records_by_id = {"receipt-1": overdue_receipt}
        FakeReceiptRepository.total = 1
        FakeOutboxRepository.list_records = [
            outbox_message,
            pending_email_message,
            stale_processing_message,
            failed_push_message,
        ]
        FakeOutboxRepository.records_by_id = {
            "outbox-1": outbox_message,
            "outbox-2": pending_email_message,
            "outbox-3": stale_processing_message,
            "outbox-4": failed_push_message,
        }
        FakeOutboxRepository.total = 4
        FakeTradeRepository.list_records = [expired_trade, active_trade]
        FakeTradeRepository.expirable_records = [expired_trade]
        FakeTradeRepository.claimable_records = [active_trade]
        FakeTradeRepository.records_by_id = {
            "trade-1": expired_trade,
            "trade-2": active_trade,
        }
        FakeTradeRepository.total = 2
        FakeOperatorRepository.operators_by_user_id = {
            9001: SimpleNamespace(
                user_id=9001,
                role=EnumValue("operator"),
                is_active=True,
                last_action_at=None,
            )
        }

        root_response = self.client.get("/v1/admin/tasks")
        self.assertEqual(root_response.status_code, 200)
        self.assertEqual(root_response.json()["areas"], ["receipts", "outbox", "emails", "trades"])
        self.assertIn("receipts:ack", root_response.json()["actions"])
        self.assertIn("emails:claim", root_response.json()["actions"])
        self.assertIn("emails:retry", root_response.json()["actions"])
        self.assertIn("outbox:retry", root_response.json()["actions"])
        self.assertIn("outbox:release-stale", root_response.json()["actions"])
        self.assertIn("trades:list", root_response.json()["actions"])
        self.assertIn("trades:claim", root_response.json()["actions"])
        self.assertIn("trades:expire", root_response.json()["actions"])

        receipts_response = self.client.get(
            "/v1/admin/tasks/receipts",
            params={
                "follow_up_status": "pending",
                "delivery_status": "failed",
                "overdue_only": True,
                "limit": 25,
                "offset": 0,
            },
        )
        self.assertEqual(receipts_response.status_code, 200)
        self.assertEqual(
            receipts_response.json(),
            {
                "data": [
                    {
                        "id": "receipt-1",
                        "notification_id": "notification-1",
                        "user_id": 42,
                        "ack_required": True,
                        "ack_deadline_at": "2026-04-04T23:45:00Z",
                        "opened_at": None,
                        "acknowledged_at": None,
                        "last_delivery_channel": "push",
                        "last_delivery_status": "failed",
                        "escalation_level": 1,
                        "manual_follow_up_status": "pending",
                        "manual_follow_up_updated_at": "2026-04-04T23:50:00Z",
                        "created_at": "2026-04-04T23:00:00Z",
                        "updated_at": "2026-04-04T23:40:00Z",
                        "overdue": True,
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        escalate_response = self.client.post(
            "/v1/admin/tasks/receipts/escalate-overdue",
            params={"limit": 20},
        )
        self.assertEqual(escalate_response.status_code, 200)
        self.assertEqual(
            escalate_response.json(),
            {"scanned": 1, "escalated": 1, "skipped": 0},
        )

        claim_response = self.client.post("/v1/admin/tasks/receipts/receipt-1/claim")
        self.assertEqual(claim_response.status_code, 200)
        self.assertEqual(claim_response.json()["message"], "Receipt follow-up claimed")
        self.assertEqual(
            claim_response.json()["receipt"]["manual_follow_up_status"],
            "claimed",
        )

        resolve_response = self.client.post("/v1/admin/tasks/receipts/receipt-1/resolve")
        self.assertEqual(resolve_response.status_code, 200)
        self.assertEqual(resolve_response.json()["message"], "Receipt follow-up resolved")
        self.assertEqual(
            resolve_response.json()["receipt"]["manual_follow_up_status"],
            "resolved",
        )

        ack_response = self.client.post(
            "/v1/admin/tasks/receipts/ack",
            json={"receipt_id": "receipt-1"},
        )
        self.assertEqual(ack_response.status_code, 200)
        self.assertEqual(ack_response.json()["message"], "Receipt acknowledged")
        self.assertEqual(ack_response.json()["receipt"]["manual_follow_up_status"], "resolved")
        self.assertEqual(ack_response.json()["receipt"]["acknowledged_at"], "2026-04-05T00:05:00Z")

        email_claim_response = self.client.post(
            "/v1/admin/tasks/emails/claim",
            params={"limit": 10},
        )
        self.assertEqual(email_claim_response.status_code, 200)
        self.assertEqual(email_claim_response.json()["message"], "Email tasks claimed")
        self.assertEqual(email_claim_response.json()["processed_count"], 1)
        self.assertEqual(email_claim_response.json()["outbox"][0]["id"], "outbox-2")
        self.assertEqual(email_claim_response.json()["outbox"][0]["status"], "processing")

        email_retry_response = self.client.post(
            "/v1/admin/tasks/emails/retry",
            json={"outbox_ids": ["outbox-2", "outbox-missing"]},
        )
        self.assertEqual(email_retry_response.status_code, 200)
        self.assertEqual(email_retry_response.json()["message"], "Email tasks requeued")
        self.assertEqual(email_retry_response.json()["processed_count"], 1)
        self.assertEqual(email_retry_response.json()["outbox"][0]["id"], "outbox-2")
        self.assertEqual(email_retry_response.json()["outbox"][0]["status"], "pending")
        self.assertEqual(email_retry_response.json()["skipped_outbox_ids"], ["outbox-missing"])

        trades_response = self.client.get(
            "/v1/admin/tasks/trades",
            params={
                "status": "pending",
                "expired_only": True,
                "user_id": 42,
                "limit": 25,
                "offset": 0,
            },
        )
        self.assertEqual(trades_response.status_code, 200)
        self.assertEqual(
            trades_response.json(),
            {
                "data": [
                    {
                        "id": "trade-1",
                        "user_id": 42,
                        "symbol": "AAPL",
                        "action": "buy",
                        "status": "pending",
                        "suggested_shares": 5.0,
                        "suggested_price": 190.25,
                        "suggested_amount": 951.25,
                        "actual_shares": None,
                        "actual_price": None,
                        "actual_amount": None,
                        "expires_at": "2026-04-04T23:55:00Z",
                        "claimed_by_operator_id": None,
                        "claimed_at": None,
                        "confirmed_at": None,
                        "created_at": "2026-04-04T22:00:00Z",
                        "updated_at": "2026-04-04T23:30:00Z",
                        "is_expired": True,
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        claim_trades_response = self.client.post(
            "/v1/admin/tasks/trades/claim",
            json={"trade_ids": ["trade-2", "trade-missing"], "limit": 10},
            headers={
                "X-Operator-ID": "9001",
                "X-Request-ID": "req-trade-claim",
            },
        )
        self.assertEqual(claim_trades_response.status_code, 200)
        self.assertEqual(claim_trades_response.json()["message"], "Trades claimed")
        self.assertEqual(claim_trades_response.json()["processed_count"], 1)
        self.assertEqual(
            claim_trades_response.json()["trades"],
            [
                {
                    "id": "trade-2",
                    "user_id": 42,
                    "symbol": "MSFT",
                    "action": "sell",
                    "status": "pending",
                    "suggested_shares": 3.0,
                    "suggested_price": 420.0,
                    "suggested_amount": 1260.0,
                    "actual_shares": None,
                    "actual_price": None,
                    "actual_amount": None,
                    "expires_at": "2026-05-05T00:00:00Z",
                    "claimed_by_operator_id": 9001,
                    "claimed_at": "2026-04-05T00:15:00Z",
                    "confirmed_at": None,
                    "created_at": "2026-04-04T23:00:00Z",
                    "updated_at": "2026-04-05T00:15:00Z",
                    "is_expired": False,
                }
            ],
        )
        self.assertEqual(claim_trades_response.json()["skipped_trade_ids"], ["trade-missing"])

        claimed_trades_response = self.client.get(
            "/v1/admin/tasks/trades",
            params={
                "claimed_only": True,
                "claimed_by_operator_id": 9001,
                "limit": 25,
                "offset": 0,
            },
        )
        self.assertEqual(claimed_trades_response.status_code, 200)
        self.assertEqual(
            claimed_trades_response.json(),
            {
                "data": [
                    {
                        "id": "trade-2",
                        "user_id": 42,
                        "symbol": "MSFT",
                        "action": "sell",
                        "status": "pending",
                        "suggested_shares": 3.0,
                        "suggested_price": 420.0,
                        "suggested_amount": 1260.0,
                        "actual_shares": None,
                        "actual_price": None,
                        "actual_amount": None,
                        "expires_at": "2026-05-05T00:00:00Z",
                        "claimed_by_operator_id": 9001,
                        "claimed_at": "2026-04-05T00:15:00Z",
                        "confirmed_at": None,
                        "created_at": "2026-04-04T23:00:00Z",
                        "updated_at": "2026-04-05T00:15:00Z",
                        "is_expired": False,
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        expire_trades_response = self.client.post(
            "/v1/admin/tasks/trades/expire",
            json={"trade_ids": ["trade-1", "trade-2"], "limit": 10},
        )
        self.assertEqual(expire_trades_response.status_code, 200)
        self.assertEqual(expire_trades_response.json()["message"], "Trades expired")
        self.assertEqual(expire_trades_response.json()["processed_count"], 1)
        self.assertEqual(expire_trades_response.json()["trades"][0]["id"], "trade-1")
        self.assertEqual(expire_trades_response.json()["trades"][0]["status"], "expired")
        self.assertEqual(expire_trades_response.json()["skipped_trade_ids"], ["trade-2"])

        outbox_response = self.client.get(
            "/v1/admin/tasks/outbox",
            params={"status": "failed", "channel": "email", "limit": 25, "offset": 0},
        )
        self.assertEqual(outbox_response.status_code, 200)
        self.assertEqual(
            outbox_response.json(),
            {
                "data": [
                    {
                        "id": "outbox-1",
                        "notification_id": "notification-1",
                        "user_id": 42,
                        "channel": "email",
                        "status": "failed",
                        "payload": {
                            "subject": "Action required",
                            "_last_error": "smtp_timeout",
                        },
                        "last_error": "smtp_timeout",
                        "created_at": "2026-04-04T23:15:00Z",
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        requeue_response = self.client.post("/v1/admin/tasks/outbox/outbox-1/requeue")
        self.assertEqual(requeue_response.status_code, 200)
        self.assertEqual(requeue_response.json()["message"], "Outbox message requeued")
        self.assertEqual(requeue_response.json()["outbox"]["status"], "pending")
        self.assertEqual(requeue_response.json()["outbox"]["last_error"], None)

        retry_response = self.client.post(
            "/v1/admin/tasks/outbox/retry",
            json={"outbox_ids": ["outbox-4", "outbox-missing"]},
        )
        self.assertEqual(retry_response.status_code, 200)
        self.assertEqual(retry_response.json()["message"], "Outbox messages requeued")
        self.assertEqual(retry_response.json()["processed_count"], 1)
        self.assertEqual(retry_response.json()["outbox"][0]["id"], "outbox-4")
        self.assertEqual(retry_response.json()["outbox"][0]["status"], "pending")
        self.assertEqual(retry_response.json()["skipped_outbox_ids"], ["outbox-missing"])

        release_stale_response = self.client.post(
            "/v1/admin/tasks/outbox/release-stale",
            params={"channel": "email", "older_than_minutes": 30, "limit": 10},
        )
        self.assertEqual(release_stale_response.status_code, 200)
        self.assertEqual(
            release_stale_response.json()["message"],
            "Stale outbox messages released",
        )
        self.assertEqual(release_stale_response.json()["processed_count"], 1)
        self.assertEqual(release_stale_response.json()["outbox"][0]["id"], "outbox-3")
        self.assertEqual(release_stale_response.json()["outbox"][0]["status"], "pending")

        self.assertEqual(
            FakeReceiptRepository.calls["list_admin_receipts"],
            [
                {
                    "limit": 25,
                    "offset": 0,
                    "follow_up_status": "pending",
                    "delivery_status": "failed",
                    "ack_required": None,
                    "overdue_only": True,
                    "user_id": None,
                    "notification_id": None,
                }
            ],
        )
        self.assertEqual(
            FakeReceiptRepository.calls["acknowledge"],
            [{"notification_id": "notification-1", "user_id": 42}],
        )
        self.assertEqual(FakeReceiptRepository.calls["list_overdue_receipts"], [20])
        self.assertEqual(
            FakeReceiptRepository.calls["mark_manual_follow_up_pending"],
            [{"receipt_id": "receipt-1", "escalation_level": 2}],
        )
        self.assertEqual(
            FakeReceiptRepository.calls["claim_manual_follow_up"],
            ["receipt-1"],
        )
        self.assertEqual(
            FakeReceiptRepository.calls["resolve_follow_up"],
            ["receipt-1"],
        )
        self.assertEqual(
            FakeOutboxRepository.calls["list_admin_messages"],
            [
                {
                    "limit": 25,
                    "offset": 0,
                    "channel": "email",
                    "status": "failed",
                    "user_id": None,
                    "notification_id": None,
                }
            ],
        )
        self.assertEqual(
            FakeTradeRepository.calls["list_admin_trades"],
            [
                {
                    "limit": 25,
                    "offset": 0,
                    "status": "pending",
                    "action": None,
                    "user_id": 42,
                    "symbol": None,
                    "expired_only": True,
                    "claimed_only": False,
                    "claimed_by_operator_id": None,
                },
                {
                    "limit": 25,
                    "offset": 0,
                    "status": None,
                    "action": None,
                    "user_id": None,
                    "symbol": None,
                    "expired_only": False,
                    "claimed_only": True,
                    "claimed_by_operator_id": 9001,
                },
            ],
        )
        self.assertEqual(
            FakeTradeRepository.calls["count_admin_trades"],
            [
                {
                    "status": "pending",
                    "action": None,
                    "user_id": 42,
                    "symbol": None,
                    "expired_only": True,
                    "claimed_only": False,
                    "claimed_by_operator_id": None,
                },
                {
                    "status": None,
                    "action": None,
                    "user_id": None,
                    "symbol": None,
                    "expired_only": False,
                    "claimed_only": True,
                    "claimed_by_operator_id": 9001,
                },
            ],
        )
        self.assertEqual(
            FakeOutboxRepository.calls["claim_pending"],
            [{"channel": "email", "limit": 10}],
        )
        self.assertEqual(
            FakeOutboxRepository.calls["release_stale_processing"],
            [{"channel": "email", "older_than_minutes": 30, "limit": 10}],
        )
        self.assertEqual(
            FakeOutboxRepository.calls["requeue"],
            ["outbox-2", "outbox-1", "outbox-4"],
        )
        self.assertEqual(
            FakeTradeRepository.calls["get_by_id"],
            ["trade-2", "trade-missing", "trade-1", "trade-2"],
        )
        self.assertEqual(
            FakeTradeRepository.calls["claim"],
            [{"trade_id": "trade-2", "operator_user_id": 9001}],
        )
        self.assertEqual(FakeTradeRepository.calls["mark_expired"], ["trade-1", "trade-2"])
        self.assertEqual(
            FakeOperatorRepository.calls["get_active_operator"],
            [{"user_id": 9001, "allowed_roles": {"operator", "admin"}}],
        )
        self.assertEqual(FakeOperatorRepository.calls["touch_operator"], [9001])
        self.assertEqual(
            FakeOutboxPublisher.events,
            [
                {
                    "topic": "ops.audit.logged",
                    "payload": {
                        "entity": "trade",
                        "entity_id": "req-trade-claim",
                        "action": "tasks.claimed",
                        "source": "admin-api",
                        "operator_id": 9001,
                        "trade_ids": ["trade-2"],
                        "skipped_trade_ids": ["trade-missing"],
                        "processed_count": 1,
                        "request_id": "req-trade-claim",
                    },
                    "key": "trade-claim:req-trade-claim",
                    "headers": {
                        "request_id": "req-trade-claim",
                        "operator_id": "9001",
                    },
                }
            ],
        )

    def test_trade_claim_requires_operator_header(self) -> None:
        response = self.client.post(
            "/v1/admin/tasks/trades/claim",
            json={"trade_ids": ["trade-1"], "limit": 10},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "admin_operator_required",
                    "message": "X-Operator-ID header is required",
                    "details": {},
                },
                "request_id": None,
            },
        )

    def test_health_routes_do_not_require_admin_auth(self) -> None:
        health_response = self.client.get("/health")
        self.assertEqual(health_response.status_code, 200)
        self.assertEqual(health_response.json()["status"], "healthy")

        readiness_response = self.client.get("/health/ready")
        self.assertEqual(readiness_response.status_code, 200)
        self.assertIn(readiness_response.json()["status"], {"ready", "degraded"})

    def test_runtime_routes_summarize_components(self) -> None:
        components = [
            {
                "component_kind": "scheduler",
                "component_name": "scheduler",
                "status": "running",
                "health": "healthy",
                "last_heartbeat_at": "2026-04-05T00:00:00Z",
                "started_at": "2026-04-04T23:00:00Z",
                "expires_at": "2026-04-05T00:00:30Z",
                "ttl_seconds": 30,
                "heartbeat_count": 4,
                "host": "node-a",
                "pid": 1234,
                "metadata": {"mode": "continuous"},
                "age_seconds": 3.5,
                "is_expected": True,
            },
            {
                "component_kind": "worker",
                "component_name": "analytics-sink",
                "status": "missing",
                "health": "missing",
                "last_heartbeat_at": None,
                "started_at": None,
                "expires_at": None,
                "ttl_seconds": None,
                "heartbeat_count": 0,
                "host": None,
                "pid": None,
                "metadata": {},
                "age_seconds": None,
                "is_expected": True,
            },
            {
                "component_kind": "worker",
                "component_name": "email-dispatch",
                "status": "failed",
                "health": "error",
                "last_heartbeat_at": "2026-04-04T23:59:30Z",
                "started_at": "2026-04-04T23:00:00Z",
                "expires_at": "2026-04-05T00:00:10Z",
                "ttl_seconds": 30,
                "heartbeat_count": 2,
                "host": "node-b",
                "pid": 2345,
                "metadata": {"error": "RuntimeError: smtp timeout"},
                "age_seconds": 18.0,
                "is_expected": True,
            },
        ]

        with (
            patch.object(runtime_router, "list_runtime_components", return_value=components),
            patch.object(runtime_router, "get_runtime_component", return_value=components[0]),
            patch.object(
                runtime_router,
                "_collect_runtime_operational_metrics",
                AsyncMock(
                    return_value=[
                        runtime_router.RuntimeMetricPointResponse(
                            name="notification_outbox_messages_total",
                            value=4.0,
                            labels={"status": "pending"},
                        ),
                        runtime_router.RuntimeMetricPointResponse(
                            name="trade_claim_latency_seconds_avg",
                            value=42.5,
                        ),
                    ]
                ),
            ),
            patch.object(
                runtime_router,
                "_collect_platform_operational_metrics",
                AsyncMock(
                    return_value=[
                        runtime_router.RuntimeMetricPointResponse(
                            name="event_broker_consumer_lag_total",
                            value=12.0,
                            labels={"backend": "kafka", "group": "stock-py.dispatchers"},
                        )
                    ]
                ),
            ),
            patch.object(
                runtime_router,
                "_collect_runtime_alerts",
                AsyncMock(
                    return_value=[
                        runtime_router.RuntimeAlertResponse(
                            severity="warning",
                            component="event-broker",
                            summary="Broker consumer lag exceeded threshold",
                            observed_value=12.0,
                            threshold=10.0,
                            labels={"backend": "kafka"},
                        )
                    ]
                ),
            ),
        ):
            list_response = self.client.get("/v1/admin/runtime/components")
            self.assertEqual(list_response.status_code, 200)
            self.assertEqual(
                list_response.json()["summary"],
                {
                    "total": 3,
                    "healthy": 1,
                    "stale": 0,
                    "missing": 1,
                    "inactive": 0,
                    "error": 1,
                },
            )
            self.assertEqual(list_response.json()["components"][0]["component_name"], "scheduler")

            stats_response = self.client.get("/v1/admin/runtime/stats")
            self.assertEqual(stats_response.status_code, 200)
            self.assertEqual(
                stats_response.json()["summary"],
                {
                    "total": 3,
                    "healthy": 1,
                    "stale": 0,
                    "missing": 1,
                    "inactive": 0,
                    "error": 1,
                },
            )
            self.assertEqual(
                stats_response.json()["by_kind"],
                {"scheduler": 1, "worker": 2},
            )
            self.assertEqual(
                stats_response.json()["by_status"],
                {"failed": 1, "missing": 1, "running": 1},
            )
            self.assertEqual(stats_response.json()["expected_components"], 3)
            self.assertEqual(stats_response.json()["reporting_components"], 2)
            self.assertEqual(stats_response.json()["coverage_percent"], 66.67)
            self.assertEqual(stats_response.json()["total_heartbeats"], 6)
            self.assertEqual(stats_response.json()["avg_age_seconds"], 10.75)
            self.assertEqual(stats_response.json()["max_age_seconds"], 18.0)
            self.assertEqual(stats_response.json()["avg_ttl_seconds"], 30.0)

            health_response = self.client.get("/v1/admin/runtime/health")
            self.assertEqual(health_response.status_code, 200)
            self.assertEqual(health_response.json()["status"], "error")
            self.assertEqual(health_response.json()["coverage_percent"], 66.67)
            self.assertEqual(
                [
                    component["component_name"]
                    for component in health_response.json()["missing_components"]
                ],
                ["analytics-sink"],
            )
            self.assertEqual(
                [
                    component["component_name"]
                    for component in health_response.json()["error_components"]
                ],
                ["email-dispatch"],
            )
            self.assertEqual(health_response.json()["stale_components"], [])

            metrics_response = self.client.get("/v1/admin/runtime/metrics")
            self.assertEqual(metrics_response.status_code, 200)
            metric_index = {
                (
                    item["name"],
                    tuple(sorted((item.get("labels") or {}).items())),
                ): item["value"]
                for item in metrics_response.json()["metrics"]
            }
            self.assertEqual(metric_index[("runtime_components_total", ())], 3.0)
            self.assertEqual(metric_index[("runtime_components_healthy", ())], 1.0)
            self.assertEqual(metric_index[("runtime_components_missing", ())], 1.0)
            self.assertEqual(metric_index[("runtime_components_error", ())], 1.0)
            self.assertEqual(metric_index[("runtime_expected_components_total", ())], 3.0)
            self.assertEqual(metric_index[("runtime_reporting_components_total", ())], 2.0)
            self.assertEqual(metric_index[("runtime_coverage_percent", ())], 66.67)
            self.assertEqual(metric_index[("runtime_heartbeats_total", ())], 6.0)
            self.assertEqual(metric_index[("runtime_component_age_seconds_avg", ())], 10.75)
            self.assertEqual(metric_index[("runtime_component_age_seconds_max", ())], 18.0)
            self.assertEqual(metric_index[("runtime_component_ttl_seconds_avg", ())], 30.0)
            self.assertEqual(
                metric_index[("runtime_components_by_kind", (("component_kind", "scheduler"),))],
                1.0,
            )
            self.assertEqual(
                metric_index[("runtime_components_by_kind", (("component_kind", "worker"),))],
                2.0,
            )
            self.assertEqual(
                metric_index[("runtime_components_by_status", (("status", "failed"),))],
                1.0,
            )
            self.assertEqual(
                metric_index[
                    (
                        "notification_outbox_messages_total",
                        (("status", "pending"),),
                    )
                ],
                4.0,
            )
            self.assertEqual(metric_index[("trade_claim_latency_seconds_avg", ())], 42.5)
            self.assertEqual(
                metric_index[
                    (
                        "event_broker_consumer_lag_total",
                        (("backend", "kafka"), ("group", "stock-py.dispatchers")),
                    )
                ],
                12.0,
            )

            alerts_response = self.client.get("/v1/admin/runtime/alerts")
            self.assertEqual(alerts_response.status_code, 200)
            self.assertEqual(
                alerts_response.json()["alerts"],
                [
                    {
                        "severity": "warning",
                        "component": "event-broker",
                        "summary": "Broker consumer lag exceeded threshold",
                        "observed_value": 12.0,
                        "threshold": 10.0,
                        "labels": {"backend": "kafka"},
                    }
                ],
            )

            detail_response = self.client.get("/v1/admin/runtime/components/scheduler/scheduler")
            self.assertEqual(detail_response.status_code, 200)
            self.assertEqual(detail_response.json()["component_kind"], "scheduler")

    def test_runtime_metrics_include_component_last_result_values(self) -> None:
        components = [
            {
                "component_kind": "worker",
                "component_name": "event-pipeline",
                "status": "completed",
                "health": "inactive",
                "last_heartbeat_at": "2026-04-05T00:00:00Z",
                "started_at": "2026-04-04T23:59:30Z",
                "expires_at": "2026-04-05T00:00:30Z",
                "ttl_seconds": 30,
                "heartbeat_count": 3,
                "host": "node-c",
                "pid": 3456,
                "metadata": {"last_result": {"claimed": 5, "published": 4, "failed": 1}},
                "age_seconds": 1.0,
                "is_expected": True,
            }
        ]

        with (
            patch.object(runtime_router, "list_runtime_components", return_value=components),
            patch.object(
                runtime_router,
                "_collect_runtime_operational_metrics",
                AsyncMock(return_value=[]),
            ),
            patch.object(
                runtime_router,
                "_collect_platform_operational_metrics",
                AsyncMock(return_value=[]),
            ),
        ):
            response = self.client.get("/v1/admin/runtime/metrics")

        self.assertEqual(response.status_code, 200)
        metric_index = {
            (
                item["name"],
                tuple(sorted((item.get("labels") or {}).items())),
            ): item["value"]
            for item in response.json()["metrics"]
        }
        self.assertEqual(
            metric_index[
                (
                    "runtime_component_last_result",
                    (
                        ("component_kind", "worker"),
                        ("component_name", "event-pipeline"),
                        ("field", "claimed"),
                    ),
                )
            ],
            5.0,
        )
        self.assertEqual(
            metric_index[
                (
                    "runtime_component_last_result",
                    (
                        ("component_kind", "worker"),
                        ("component_name", "event-pipeline"),
                        ("field", "published"),
                    ),
                )
            ],
            4.0,
        )


if __name__ == "__main__":
    unittest.main()
