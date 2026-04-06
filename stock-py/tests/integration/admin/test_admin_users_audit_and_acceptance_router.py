from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.admin_api.routers import acceptance as acceptance_router
from apps.admin_api.routers import audit as audit_router
from apps.admin_api.routers import users as users_router
from infra.core.errors import register_exception_handlers
from infra.db.session import get_db_session


class FakeUserRepository:
    users_by_id: dict[int, SimpleNamespace] = {}
    accounts_by_user_id: dict[int, SimpleNamespace] = {}

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.users_by_id = {}
        cls.accounts_by_user_id = {}

    @classmethod
    def _filtered_users(
        cls,
        *,
        query: str | None = None,
        plan: str | None = None,
        is_active: bool | None = None,
    ) -> list[SimpleNamespace]:
        users = sorted(cls.users_by_id.values(), key=lambda item: item.id)
        if query:
            lowered = query.lower()
            users = [
                user
                for user in users
                if lowered in user.email.lower()
                or lowered in str(getattr(user, "name", "") or "").lower()
            ]
        if plan:
            users = [user for user in users if user.plan == plan]
        if is_active is not None:
            users = [user for user in users if bool(user.is_active) is is_active]
        return users

    async def list_admin_users(self, **kwargs):
        users = self._filtered_users(
            query=kwargs.get("query"),
            plan=kwargs.get("plan"),
            is_active=kwargs.get("is_active"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(users)) or len(users))
        return [
            (user, self.accounts_by_user_id.get(user.id)) for user in users[offset : offset + limit]
        ]

    async def count_admin_users(self, **kwargs):
        return len(
            self._filtered_users(
                query=kwargs.get("query"),
                plan=kwargs.get("plan"),
                is_active=kwargs.get("is_active"),
            )
        )

    async def get_admin_user_detail(self, user_id: int):
        user = self.users_by_id.get(user_id)
        return user, self.accounts_by_user_id.get(user_id)

    async def update_admin_user(self, user_id: int, **kwargs):
        user = self.users_by_id.get(user_id)
        if user is None:
            return None
        for field, value in kwargs.items():
            if field == "timezone_name" and value is not None:
                user.timezone = value
            elif value is not None:
                setattr(user, field, value)
        user.updated_at = datetime(2026, 4, 5, 2, 0, tzinfo=timezone.utc)
        if kwargs.get("extra") is not None:
            payload = dict(user.extra or {})
            payload.update(kwargs["extra"])
            user.extra = payload
        return user

    async def bulk_update_admin_users(self, user_ids: list[int], **kwargs):
        updated_ids: list[int] = []
        for user_id in user_ids:
            user = self.users_by_id.get(user_id)
            if user is None:
                continue
            if kwargs.get("plan") is not None:
                user.plan = kwargs["plan"]
            if kwargs.get("is_active") is not None:
                user.is_active = kwargs["is_active"]
            user.updated_at = datetime(2026, 4, 5, 3, 0, tzinfo=timezone.utc)
            updated_ids.append(user_id)
        return updated_ids

    async def list_admin_users_by_ids(self, user_ids: list[int]):
        rows = []
        for user_id in user_ids:
            user = self.users_by_id.get(user_id)
            if user is None:
                continue
            rows.append((user, self.accounts_by_user_id.get(user_id)))
        return rows


class FakeAccountRepository:
    def __init__(self, db) -> None:
        self.db = db

    async def upsert_account(self, user_id: int, **kwargs):
        account = FakeUserRepository.accounts_by_user_id.get(user_id)
        if account is None:
            account = SimpleNamespace(user_id=user_id, total_capital=None, currency=None)
            FakeUserRepository.accounts_by_user_id[user_id] = account
        if kwargs.get("total_capital") is not None:
            account.total_capital = kwargs["total_capital"]
        if kwargs.get("currency") is not None:
            account.currency = kwargs["currency"]
        return account


class FakeEventOutboxRepository:
    records: list[SimpleNamespace] = []

    def __init__(self, db) -> None:
        self.db = db

    @classmethod
    def reset(cls) -> None:
        cls.records = []

    @classmethod
    def _filtered(
        cls,
        *,
        entity: str | None = None,
        entity_id: str | None = None,
        action: str | None = None,
        source: str | None = None,
        status: str | None = None,
        request_id: str | None = None,
    ) -> list[SimpleNamespace]:
        items = list(cls.records)
        if entity:
            items = [item for item in items if str(item.payload.get("entity") or "") == entity]
        if entity_id:
            items = [
                item for item in items if str(item.payload.get("entity_id") or "") == entity_id
            ]
        if action:
            items = [item for item in items if str(item.payload.get("action") or "") == action]
        if source:
            items = [item for item in items if str(item.payload.get("source") or "") == source]
        if status:
            items = [item for item in items if str(item.status) == status]
        if request_id:
            items = [
                item
                for item in items
                if str(item.headers.get("request_id") or item.payload.get("request_id") or "")
                == request_id
            ]
        return items

    async def list_audit_events(self, **kwargs):
        items = self._filtered(
            entity=kwargs.get("entity"),
            entity_id=kwargs.get("entity_id"),
            action=kwargs.get("action"),
            source=kwargs.get("source"),
            status=kwargs.get("status"),
            request_id=kwargs.get("request_id"),
        )
        offset = int(kwargs.get("offset", 0) or 0)
        limit = int(kwargs.get("limit", len(items)) or len(items))
        return list(items[offset : offset + limit])

    async def count_audit_events(self, **kwargs):
        return len(
            self._filtered(
                entity=kwargs.get("entity"),
                entity_id=kwargs.get("entity_id"),
                action=kwargs.get("action"),
                source=kwargs.get("source"),
                status=kwargs.get("status"),
                request_id=kwargs.get("request_id"),
            )
        )


class AdminUsersAuditAndAcceptanceRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        FakeUserRepository.reset()
        FakeEventOutboxRepository.reset()

        self.tmpdir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmpdir.name)
        self._seed_acceptance_artifacts(self.repo_root)

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(users_router.router)
        self.app.include_router(audit_router.router)
        self.app.include_router(acceptance_router.router)

        async def override_db_session():
            yield object()

        self.app.dependency_overrides[get_db_session] = override_db_session

        self.user_repository_patch = patch.object(
            users_router, "UserRepository", FakeUserRepository
        )
        self.account_repository_patch = patch.object(
            users_router, "AccountRepository", FakeAccountRepository
        )
        self.audit_repository_patch = patch.object(
            audit_router, "EventOutboxRepository", FakeEventOutboxRepository
        )
        self.acceptance_root_patch = patch.object(acceptance_router, "REPO_ROOT", self.repo_root)

        self.user_repository_patch.start()
        self.account_repository_patch.start()
        self.audit_repository_patch.start()
        self.acceptance_root_patch.start()

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.user_repository_patch.stop()
        self.account_repository_patch.stop()
        self.audit_repository_patch.stop()
        self.acceptance_root_patch.stop()
        self.tmpdir.cleanup()

    def test_users_routes_list_detail_update_and_bulk(self) -> None:
        created_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
        FakeUserRepository.users_by_id = {
            1: SimpleNamespace(
                id=1,
                email="admin@example.com",
                name="Admin User",
                plan="pro",
                locale="en",
                timezone="UTC",
                extra={"subscription": {"status": "trialing"}},
                is_active=True,
                last_login_at=created_at + timedelta(hours=12),
                created_at=created_at,
                updated_at=created_at + timedelta(days=1),
            ),
            2: SimpleNamespace(
                id=2,
                email="ops@example.com",
                name="Ops User",
                plan="free",
                locale="zh-TW",
                timezone="Asia/Taipei",
                extra={},
                is_active=False,
                last_login_at=None,
                created_at=created_at + timedelta(days=2),
                updated_at=created_at + timedelta(days=2),
            ),
        }
        FakeUserRepository.accounts_by_user_id = {
            1: SimpleNamespace(user_id=1, total_capital=250000.0, currency="USD"),
            2: SimpleNamespace(user_id=2, total_capital=90000.0, currency="TWD"),
        }

        list_response = self.client.get(
            "/v1/admin/users",
            params={"query": "admin", "plan": "pro", "is_active": True},
        )
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(
            list_response.json(),
            {
                "data": [
                    {
                        "id": 1,
                        "email": "admin@example.com",
                        "name": "Admin User",
                        "plan": "pro",
                        "locale": "en",
                        "timezone": "UTC",
                        "subscription_status": "trialing",
                        "extra": {"subscription": {"status": "trialing"}},
                        "is_active": True,
                        "total_capital": 250000.0,
                        "currency": "USD",
                        "last_login_at": "2026-04-01T12:00:00Z",
                        "created_at": "2026-04-01T00:00:00Z",
                        "updated_at": "2026-04-02T00:00:00Z",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        )

        detail_response = self.client.get("/v1/admin/users/2")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.json(),
            {
                "id": 2,
                "email": "ops@example.com",
                "name": "Ops User",
                "plan": "free",
                "locale": "zh-TW",
                "timezone": "Asia/Taipei",
                "subscription_status": None,
                "extra": {},
                "is_active": False,
                "total_capital": 90000.0,
                "currency": "TWD",
                "last_login_at": None,
                "created_at": "2026-04-03T00:00:00Z",
                "updated_at": "2026-04-03T00:00:00Z",
            },
        )

        update_response = self.client.put(
            "/v1/admin/users/2",
            json={
                "plan": "enterprise",
                "is_active": True,
                "total_capital": 120000.0,
                "currency": "USD",
                "extra": {"subscription": {"status": "active"}},
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.assertEqual(
            update_response.json(),
            {
                "id": 2,
                "email": "ops@example.com",
                "name": "Ops User",
                "plan": "enterprise",
                "locale": "zh-TW",
                "timezone": "Asia/Taipei",
                "subscription_status": "active",
                "extra": {"subscription": {"status": "active"}},
                "is_active": True,
                "total_capital": 120000.0,
                "currency": "USD",
                "last_login_at": None,
                "created_at": "2026-04-03T00:00:00Z",
                "updated_at": "2026-04-05T02:00:00Z",
            },
        )

        bulk_response = self.client.post(
            "/v1/admin/users/bulk",
            json={"user_ids": [2], "plan": "pro", "is_active": True},
        )
        self.assertEqual(bulk_response.status_code, 200)
        self.assertEqual(
            bulk_response.json(),
            {
                "message": "Users updated",
                "updated_user_ids": [2],
                "users": [
                    {
                        "id": 2,
                        "email": "ops@example.com",
                        "name": "Ops User",
                        "plan": "pro",
                        "locale": "zh-TW",
                        "timezone": "Asia/Taipei",
                        "subscription_status": "active",
                        "extra": {"subscription": {"status": "active"}},
                        "is_active": True,
                        "total_capital": 120000.0,
                        "currency": "USD",
                        "last_login_at": None,
                        "created_at": "2026-04-03T00:00:00Z",
                        "updated_at": "2026-04-05T03:00:00Z",
                    }
                ],
            },
        )

    def test_audit_route_lists_filtered_rows(self) -> None:
        now = datetime(2026, 4, 5, tzinfo=timezone.utc)
        FakeEventOutboxRepository.records = [
            SimpleNamespace(
                id="evt-1",
                topic="ops.audit.logged",
                event_key="signals:AAPL",
                status="published",
                payload={
                    "entity": "signals",
                    "entity_id": "301",
                    "action": "generated",
                    "source": "scanner",
                    "symbol": "AAPL",
                },
                headers={"request_id": "req-123"},
                attempt_count=1,
                last_error=None,
                occurred_at=now - timedelta(minutes=15),
                published_at=now - timedelta(minutes=10),
                created_at=now - timedelta(minutes=15),
            ),
            SimpleNamespace(
                id="evt-2",
                topic="ops.audit.logged",
                event_key="market_data:BTCUSDT",
                status="pending",
                payload={
                    "entity": "market_data",
                    "entity_id": "import-77",
                    "action": "imported",
                    "source": "polygon",
                },
                headers={"request_id": "req-999"},
                attempt_count=0,
                last_error=None,
                occurred_at=now - timedelta(minutes=5),
                published_at=None,
                created_at=now - timedelta(minutes=5),
            ),
        ]

        response = self.client.get(
            "/v1/admin/audit",
            params={"entity": "market_data", "action": "imported", "status": "pending"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "data": [
                    {
                        "id": "evt-2",
                        "topic": "ops.audit.logged",
                        "event_key": "market_data:BTCUSDT",
                        "status": "pending",
                        "entity": "market_data",
                        "entity_id": "import-77",
                        "action": "imported",
                        "source": "polygon",
                        "request_id": "req-999",
                        "payload": {
                            "entity": "market_data",
                            "entity_id": "import-77",
                            "action": "imported",
                            "source": "polygon",
                        },
                        "headers": {"request_id": "req-999"},
                        "attempt_count": 0,
                        "last_error": None,
                        "occurred_at": "2026-04-04T23:55:00Z",
                        "published_at": None,
                        "created_at": "2026-04-04T23:55:00Z",
                    }
                ],
                "total": 1,
                "limit": 50,
                "offset": 0,
                "has_more": False,
            },
        )

    def test_acceptance_routes_report_current_readiness(self) -> None:
        status_response = self.client.get("/v1/admin/acceptance/status")
        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(
            status_response.json(),
            {
                "qa_workflow_ready": True,
                "qa_runbook_ready": True,
                "public_openapi_snapshot_ready": True,
                "admin_openapi_snapshot_ready": True,
                "load_template_ready": True,
                "cutover_template_ready": True,
                "reviewed_load_reports": 1,
                "reviewed_cutover_reports": 1,
                "latest_load_report": "ops/reports/load/20260405/baseline-summary.md",
                "latest_cutover_report": "ops/reports/cutover/20260405/canary-rollback-rehearsal.md",
                "acceptance_ready": True,
            },
        )

        report_response = self.client.get("/v1/admin/acceptance/report")
        self.assertEqual(report_response.status_code, 200)
        payload = report_response.json()
        self.assertEqual(payload["status"]["acceptance_ready"], True)
        self.assertEqual(
            payload["commands"],
            [
                "make qa-ci",
                "make load-report-init",
                "make cutover-report-init",
                "make cutover-openapi-diff",
            ],
        )
        self.assertEqual(payload["automation_artifacts"][0]["path"], ".github/workflows/qa.yml")
        self.assertEqual(
            payload["openapi_snapshots"][1]["path"],
            "tests/contract/snapshots/admin_api_openapi_manifest.json",
        )
        self.assertEqual(
            payload["load_reports"][0]["path"], "ops/reports/load/20260405/baseline-summary.md"
        )
        self.assertEqual(
            payload["cutover_reports"][0]["path"],
            "ops/reports/cutover/20260405/canary-rollback-rehearsal.md",
        )

    def _seed_acceptance_artifacts(self, repo_root: Path) -> None:
        self._write(repo_root / ".github/workflows/qa.yml", "name: qa\n")
        self._write(repo_root / "ops/runbooks/qa-cutover-checklist.md", "# QA Cutover Checklist\n")
        self._write(
            repo_root / "tests/contract/snapshots/public_api_openapi_manifest.json",
            "{}\n",
        )
        self._write(
            repo_root / "tests/contract/snapshots/admin_api_openapi_manifest.json",
            "{}\n",
        )
        self._write(
            repo_root / "ops/reports/load/baseline-summary-template.md",
            "# Baseline Summary Template\n",
        )
        self._write(
            repo_root / "ops/reports/cutover/canary-rollback-rehearsal-template.md",
            "# Canary Rollback Rehearsal Template\n",
        )
        self._write(
            repo_root / "ops/reports/load/20260405/baseline-summary.md",
            "# Baseline Summary\n",
        )
        self._write(
            repo_root / "ops/reports/cutover/20260405/canary-rollback-rehearsal.md",
            "# Canary Rollback Rehearsal\n",
        )

    def _write(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
