from __future__ import annotations

import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routers import distribution as distribution_router
from apps.admin_api.routers import operators as operators_router
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class EnumValue:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeOperatorRepository:
    users_by_id = {}
    operators_by_user_id = {}
    calls: dict[str, list] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.users_by_id = {}
        cls.operators_by_user_id = {}
        cls.calls = {
            "list_admin_operators": [],
            "count_admin_operators": [],
            "upsert_operator": [],
            "get_active_operator": [],
            "touch_operator": [],
        }

    @classmethod
    def _filtered_rows(
        cls,
        *,
        query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ):
        rows = []
        for user_id, operator in cls.operators_by_user_id.items():
            user = cls.users_by_id.get(user_id)
            if user is None:
                continue
            rows.append((operator, user))

        if query:
            normalized = query.strip().lower()
            rows = [
                row
                for row in rows
                if normalized in str(row[1].email).lower()
                or normalized in str(getattr(row[1], "name", "") or "").lower()
            ]
        if role:
            rows = [row for row in rows if str(getattr(row[0].role, "value", row[0].role)) == role]
        if is_active is not None:
            rows = [row for row in rows if bool(row[0].is_active) is is_active]
        rows.sort(key=lambda row: int(row[0].user_id))
        return rows

    async def list_admin_operators(self, **kwargs):
        self.calls["list_admin_operators"].append(kwargs)
        rows = self._filtered_rows(
            query=kwargs.get("query"),
            role=kwargs.get("role"),
            is_active=kwargs.get("is_active"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(rows)) or len(rows))
        return list(rows[offset : offset + limit])

    async def count_admin_operators(self, **kwargs):
        self.calls["count_admin_operators"].append(kwargs)
        return len(
            self._filtered_rows(
                query=kwargs.get("query"),
                role=kwargs.get("role"),
                is_active=kwargs.get("is_active"),
            )
        )

    async def upsert_operator(
        self,
        user_id: int,
        *,
        role: str | None = None,
        scopes: list[str] | None = None,
        is_active: bool | None = None,
    ):
        self.calls["upsert_operator"].append(
            {
                "user_id": user_id,
                "role": role,
                "scopes": scopes,
                "is_active": is_active,
            }
        )
        user = self.users_by_id.get(user_id)
        if user is None:
            return None, None

        operator = self.operators_by_user_id.get(user_id)
        if operator is None:
            operator = SimpleNamespace(
                user_id=user_id,
                role=EnumValue(role or "viewer"),
                scopes=list(scopes or []),
                is_active=True if is_active is None else bool(is_active),
                last_action_at=None,
                created_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
            )
            self.operators_by_user_id[user_id] = operator

        if role is not None:
            operator.role = EnumValue(role)
        if scopes is not None:
            operator.scopes = list(scopes)
        if is_active is not None:
            operator.is_active = bool(is_active)
        operator.updated_at = datetime(2026, 4, 5, 0, 20, tzinfo=timezone.utc)
        return operator, user

    async def get_active_operator(self, user_id: int, *, allowed_roles: set[str] | None = None):
        self.calls["get_active_operator"].append(
            {"user_id": user_id, "allowed_roles": allowed_roles}
        )
        operator = self.operators_by_user_id.get(user_id)
        user = self.users_by_id.get(user_id)
        if operator is None or user is None or not bool(operator.is_active):
            return None, None
        role = str(getattr(operator.role, "value", operator.role))
        if allowed_roles is not None and role not in allowed_roles:
            return None, None
        return operator, user

    async def touch_operator(self, user_id: int):
        self.calls["touch_operator"].append(user_id)
        operator = self.operators_by_user_id.get(user_id)
        if operator is None:
            return None
        operator.last_action_at = datetime(2026, 4, 5, 0, 25, tzinfo=timezone.utc)
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


class FakeManualDistributionService:
    calls: list[dict] = []
    return_value = None

    def __init__(self, session) -> None:
        self.session = session

    @classmethod
    def reset(cls) -> None:
        cls.calls = []
        cls.return_value = SimpleNamespace(
            created_notifications=2,
            requested_outbox=4,
            resolved_user_ids=[2, 3],
            skipped_user_ids=[99],
            notification_ids=["notification-1", "notification-2"],
            outbox_ids=["outbox-1", "outbox-2", "outbox-3", "outbox-4"],
        )

    async def send_manual_message(self, **kwargs):
        self.calls.append(kwargs)
        return self.return_value


class AdminDistributionAndOperatorsRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeOperatorRepository.reset()
        FakeOutboxPublisher.reset()
        FakeManualDistributionService.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(operators_router.router)
        self.app.include_router(distribution_router.router)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session

        self.operators_repository_patch = patch.object(
            operators_router,
            "OperatorRepository",
            FakeOperatorRepository,
        )
        self.operators_outbox_patch = patch.object(
            operators_router,
            "OutboxPublisher",
            FakeOutboxPublisher,
        )
        self.distribution_repository_patch = patch.object(
            distribution_router,
            "OperatorRepository",
            FakeOperatorRepository,
        )
        self.distribution_service_patch = patch.object(
            distribution_router,
            "ManualDistributionService",
            FakeManualDistributionService,
        )

        self.operators_repository_patch.start()
        self.operators_outbox_patch.start()
        self.distribution_repository_patch.start()
        self.distribution_service_patch.start()
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.operators_repository_patch.stop()
        self.operators_outbox_patch.stop()
        self.distribution_repository_patch.stop()
        self.distribution_service_patch.stop()

    def test_operator_routes_list_and_update(self) -> None:
        FakeOperatorRepository.users_by_id = {
            2: SimpleNamespace(id=2, email="ops@example.com", name="Ops User"),
            9001: SimpleNamespace(id=9001, email="admin@example.com", name="Admin User"),
        }
        FakeOperatorRepository.operators_by_user_id = {
            2: SimpleNamespace(
                user_id=2,
                role=EnumValue("operator"),
                scopes=["tasks.trades", "distribution.manual"],
                is_active=True,
                last_action_at=datetime(2026, 4, 5, 0, 10, tzinfo=timezone.utc),
                created_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 5, 0, 5, tzinfo=timezone.utc),
            ),
            9001: SimpleNamespace(
                user_id=9001,
                role=EnumValue("admin"),
                scopes=["*"],
                is_active=True,
                last_action_at=None,
                created_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
            ),
        }

        list_response = self.client.get(
            "/v1/admin/operators",
            params={"query": "ops", "role": "operator", "is_active": True, "limit": 25},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "data": [
                    {
                        "user_id": 2,
                        "email": "ops@example.com",
                        "name": "Ops User",
                        "role": "operator",
                        "scopes": ["tasks.trades", "distribution.manual"],
                        "is_active": True,
                        "last_action_at": "2026-04-05T00:10:00Z",
                        "created_at": "2026-04-04T00:00:00Z",
                        "updated_at": "2026-04-05T00:05:00Z",
                    }
                ],
                "total": 1,
                "limit": 25,
                "offset": 0,
                "has_more": False,
            },
        )

        update_response = self.client.put(
            "/v1/admin/operators/2",
            json={
                "role": "admin",
                "scopes": ["distribution.manual", "tasks.trades"],
                "is_active": False,
            },
            headers={
                "X-Operator-ID": "9001",
                "X-Request-ID": "req-operator-1",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json(),
            {
                "user_id": 2,
                "email": "ops@example.com",
                "name": "Ops User",
                "role": "admin",
                "scopes": ["distribution.manual", "tasks.trades"],
                "is_active": False,
                "last_action_at": "2026-04-05T00:10:00Z",
                "created_at": "2026-04-04T00:00:00Z",
                "updated_at": "2026-04-05T00:20:00Z",
            },
        )

        self.assertEqual(
            FakeOperatorRepository.calls["list_admin_operators"],
            [{"limit": 25, "offset": 0, "query": "ops", "role": "operator", "is_active": True}],
        )
        self.assertEqual(
            FakeOperatorRepository.calls["count_admin_operators"],
            [{"query": "ops", "role": "operator", "is_active": True}],
        )
        self.assertEqual(
            FakeOperatorRepository.calls["upsert_operator"],
            [
                {
                    "user_id": 2,
                    "role": "admin",
                    "scopes": ["distribution.manual", "tasks.trades"],
                    "is_active": False,
                }
            ],
        )
        self.assertEqual(
            FakeOutboxPublisher.events,
            [
                {
                    "topic": "ops.audit.logged",
                    "payload": {
                        "entity": "operator",
                        "entity_id": "2",
                        "action": "role.updated",
                        "source": "admin-api",
                        "operator_id": "9001",
                        "role": "admin",
                        "scopes": ["distribution.manual", "tasks.trades"],
                        "is_active": False,
                        "request_id": "req-operator-1",
                    },
                    "key": "operator:2",
                    "headers": {
                        "request_id": "req-operator-1",
                        "operator_id": "9001",
                    },
                }
            ],
        )

    def test_manual_distribution_route_queues_message(self) -> None:
        FakeOperatorRepository.users_by_id = {
            9001: SimpleNamespace(id=9001, email="operator@example.com", name="Operator User")
        }
        FakeOperatorRepository.operators_by_user_id = {
            9001: SimpleNamespace(
                user_id=9001,
                role=EnumValue("operator"),
                scopes=["distribution.manual"],
                is_active=True,
                last_action_at=None,
                created_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
                updated_at=datetime(2026, 4, 4, 0, 0, tzinfo=timezone.utc),
            )
        }

        response = self.client.post(
            "/v1/admin/distribution/manual-message",
            json={
                "user_ids": [2, 3, 99, 2],
                "title": "Action required",
                "body": "Review the pending trade queue.",
                "channels": ["push", "email", "push"],
                "notification_type": "manual.message",
                "ack_required": True,
                "ack_deadline_at": "2026-04-06T00:00:00Z",
                "metadata": {"campaign": "april-ops"},
            },
            headers={
                "X-Operator-ID": "9001",
                "X-Request-ID": "req-distribution-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "message": "Manual distribution message queued",
                "created_notifications": 2,
                "requested_outbox": 4,
                "resolved_user_ids": [2, 3],
                "skipped_user_ids": [99],
                "notification_ids": ["notification-1", "notification-2"],
                "outbox_ids": ["outbox-1", "outbox-2", "outbox-3", "outbox-4"],
                "channels": ["email", "push"],
            },
        )

        self.assertEqual(
            FakeOperatorRepository.calls["get_active_operator"],
            [{"user_id": 9001, "allowed_roles": {"operator", "admin"}}],
        )
        self.assertEqual(FakeOperatorRepository.calls["touch_operator"], [9001])
        self.assertEqual(len(FakeManualDistributionService.calls), 1)
        call = FakeManualDistributionService.calls[0]
        self.assertEqual(call["operator_user_id"], 9001)
        self.assertEqual(call["context"].request_id, "req-distribution-1")
        self.assertEqual(call["context"].operator_id, "9001")
        self.assertEqual(call["user_ids"], [2, 3, 99, 2])
        self.assertEqual(call["title"], "Action required")
        self.assertEqual(call["body"], "Review the pending trade queue.")
        self.assertEqual(call["channels"], ["email", "push"])
        self.assertEqual(call["notification_type"], "manual.message")
        self.assertEqual(call["ack_required"], True)
        self.assertEqual(call["ack_deadline_at"].isoformat(), "2026-04-06T00:00:00+00:00")
        self.assertEqual(call["metadata"], {"campaign": "april-ops"})

    def test_manual_distribution_rejects_invalid_channels(self) -> None:
        response = self.client.post(
            "/v1/admin/distribution/manual-message",
            json={
                "user_ids": [2],
                "title": "Action required",
                "body": "Review the pending trade queue.",
                "channels": ["sms"],
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json(),
            {
                "error": {
                    "code": "admin_distribution_channel_invalid",
                    "message": "Unsupported channels: sms",
                    "details": {},
                },
                "request_id": None,
            },
        )
        self.assertEqual(FakeOperatorRepository.calls["get_active_operator"], [])
        self.assertEqual(FakeManualDistributionService.calls, [])


if __name__ == "__main__":
    unittest.main()
