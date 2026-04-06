import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, patch

from domains.auth.repository import EmailCodeRepository, SessionRepository
from infra.security.auth import require_user
from infra.security.session_cache import (
    SessionCacheDelete,
    SessionCacheUpsert,
    pop_pending_session_cache_operations,
)


class FakeScalarResult:
    def __init__(self, scalar=None, values=None) -> None:
        self._scalar = scalar
        self._values = list(values or [])

    def scalar_one_or_none(self):
        return self._scalar

    def scalars(self):
        return SimpleNamespace(all=lambda: list(self._values))


class FakeSession:
    def __init__(self, results=None) -> None:
        self.info = {}
        self.results = list(results or [])
        self.added = []
        self.executed = []
        self.flush_calls = 0

    def add(self, model) -> None:
        self.added.append(model)

    async def flush(self) -> None:
        self.flush_calls += 1

    async def execute(self, statement):
        self.executed.append(statement)
        if not self.results:
            return FakeScalarResult()
        return self.results.pop(0)


class SessionRepositoryCacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_create_session_schedules_cache_upsert(self) -> None:
        session = FakeSession()
        repository = SessionRepository(session)
        expires_at = datetime.now(UTC) + timedelta(minutes=30)

        await repository.create_session(
            token_hash="token-hash-1",
            user_id=42,
            expires_at=expires_at,
            device_info={"kind": "access"},
        )

        operations = pop_pending_session_cache_operations(session)

        self.assertEqual(len(session.added), 1)
        self.assertEqual(session.flush_calls, 1)
        self.assertEqual(len(operations), 1)
        self.assertIsInstance(operations[0], SessionCacheUpsert)
        self.assertEqual(operations[0].token_hash, "token-hash-1")
        self.assertEqual(operations[0].user_id, 42)
        self.assertEqual(operations[0].expires_at, expires_at)

    async def test_revoke_for_user_schedules_cache_delete_for_existing_hashes(self) -> None:
        session = FakeSession(
            results=[FakeScalarResult(values=["hash-a", "hash-b"]), FakeScalarResult()]
        )
        repository = SessionRepository(session)

        await repository.revoke_for_user(42)

        operations = pop_pending_session_cache_operations(session)

        self.assertEqual(session.flush_calls, 1)
        self.assertEqual(len(session.executed), 2)
        self.assertEqual(len(operations), 1)
        self.assertIsInstance(operations[0], SessionCacheDelete)
        self.assertEqual(operations[0].token_hashes, ("hash-a", "hash-b"))

    async def test_get_active_user_id_by_token_hash_uses_cache_before_db_lookup(self) -> None:
        session = SimpleNamespace(
            execute=AsyncMock(side_effect=AssertionError("DB should not be queried"))
        )
        repository = SessionRepository(session)

        with patch(
            "domains.auth.repository.get_cached_session_user_id",
            new=AsyncMock(return_value=42),
        ):
            user_id = await repository.get_active_user_id_by_token_hash("hash-a")

        self.assertEqual(user_id, 42)

    async def test_get_active_user_id_by_token_hash_backfills_cache_after_db_lookup(self) -> None:
        expires_at = datetime.now(UTC) + timedelta(minutes=30)
        session_record = SimpleNamespace(user_id=42, expires_at=expires_at)
        session = FakeSession(results=[FakeScalarResult(scalar=session_record)])
        repository = SessionRepository(session)

        with (
            patch(
                "domains.auth.repository.get_cached_session_user_id",
                new=AsyncMock(return_value=None),
            ),
            patch("domains.auth.repository.cache_active_session", new=AsyncMock()) as cache_active,
        ):
            user_id = await repository.get_active_user_id_by_token_hash("hash-a")

        self.assertEqual(user_id, 42)
        cache_active.assert_awaited_once_with("hash-a", 42, expires_at)


class EmailCodeRepositoryCleanupTest(unittest.IsolatedAsyncioTestCase):
    async def test_delete_expired_if_due_skips_when_lease_not_acquired(self) -> None:
        session = FakeSession()
        repository = EmailCodeRepository(session)
        client = SimpleNamespace(set=AsyncMock(return_value=False))

        with patch("domains.auth.repository.get_redis", new=AsyncMock(return_value=client)):
            deleted = await repository.delete_expired_if_due(interval_seconds=300)

        self.assertFalse(deleted)
        self.assertEqual(session.flush_calls, 0)
        self.assertEqual(session.executed, [])

    async def test_delete_expired_if_due_runs_cleanup_when_lease_acquired(self) -> None:
        session = FakeSession(results=[FakeScalarResult()])
        repository = EmailCodeRepository(session)
        client = SimpleNamespace(set=AsyncMock(return_value=True))

        with patch("domains.auth.repository.get_redis", new=AsyncMock(return_value=client)):
            deleted = await repository.delete_expired_if_due(interval_seconds=300)

        self.assertTrue(deleted)
        self.assertEqual(session.flush_calls, 1)
        self.assertEqual(len(session.executed), 1)


class RequireUserCacheTest(unittest.IsolatedAsyncioTestCase):
    async def test_require_user_uses_session_cache_before_db_lookup(self) -> None:
        session = SimpleNamespace(
            execute=AsyncMock(side_effect=AssertionError("DB should not be queried"))
        )
        credentials = SimpleNamespace(credentials="access-token")
        signer = SimpleNamespace(
            verify=lambda token: {
                "sub": "42",
                "type": "access",
                "plan": "pro",
                "scopes": ["app"],
                "is_admin": False,
            }
        )

        with (
            patch("infra.security.auth.get_token_signer", return_value=signer),
            patch("infra.security.auth.get_cached_session_user_id", new=AsyncMock(return_value=42)),
        ):
            user = await require_user(credentials=credentials, session=session)

        self.assertEqual(user.user_id, 42)
        self.assertEqual(user.plan, "pro")

    async def test_require_user_backfills_cache_after_db_lookup(self) -> None:
        expires_at = datetime.now(UTC) + timedelta(minutes=30)
        session_record = SimpleNamespace(user_id=42, expires_at=expires_at)
        session = SimpleNamespace(
            execute=AsyncMock(return_value=FakeScalarResult(scalar=session_record))
        )
        credentials = SimpleNamespace(credentials="access-token")
        signer = SimpleNamespace(
            verify=lambda token: {
                "sub": "42",
                "type": "access",
                "plan": "pro",
                "scopes": ["app"],
                "is_admin": False,
            }
        )

        with (
            patch("infra.security.auth.get_token_signer", return_value=signer),
            patch(
                "infra.security.auth.get_cached_session_user_id", new=AsyncMock(return_value=None)
            ),
            patch("infra.security.auth.cache_active_session", new=AsyncMock()) as cache_active,
        ):
            user = await require_user(credentials=credentials, session=session)

        self.assertEqual(user.user_id, 42)
        cache_active.assert_awaited_once_with(ANY, 42, expires_at)


if __name__ == "__main__":
    unittest.main()
