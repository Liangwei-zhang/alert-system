import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from domains.auth.service import AuthService
from infra.core.errors import AppError


class AuthServiceHotPathTest(unittest.IsolatedAsyncioTestCase):
    async def test_send_code_uses_due_cleanup_instead_of_full_sweep_every_time(self) -> None:
        service = AuthService(SimpleNamespace())
        service.policy = SimpleNamespace(
            validate_send_code_limit=AsyncMock(),
            can_return_dev_code=lambda: True,
        )
        service.email_code_repository = SimpleNamespace(
            delete_expired_if_due=AsyncMock(return_value=False),
            create_code=AsyncMock(),
        )

        response = await service.send_code(" User@example.com ", ip="203.0.113.10")

        service.policy.validate_send_code_limit.assert_awaited_once_with("user@example.com")
        service.email_code_repository.delete_expired_if_due.assert_awaited_once_with()
        service.email_code_repository.create_code.assert_awaited_once()
        self.assertEqual(
            service.email_code_repository.create_code.await_args.kwargs["email"], "user@example.com"
        )
        self.assertEqual(
            service.email_code_repository.create_code.await_args.kwargs["ip"], "203.0.113.10"
        )
        self.assertIsNotNone(response.dev_code)

    async def test_refresh_uses_active_user_id_lookup(self) -> None:
        service = AuthService(SimpleNamespace())
        service.session_repository = SimpleNamespace(
            get_active_user_id_by_token_hash=AsyncMock(return_value=42),
            create_session=AsyncMock(),
            rotate_refresh_session=AsyncMock(),
        )
        service.user_repository = SimpleNamespace(
            get_by_id=AsyncMock(
                return_value=SimpleNamespace(
                    id=42,
                    email="user@example.com",
                    name="QA User",
                    plan="pro",
                    locale="en-US",
                    timezone="UTC",
                    is_active=True,
                )
            )
        )
        service.token_signer = SimpleNamespace(
            verify=lambda token: {"type": "refresh", "sub": "42"},
            sign=lambda user_id, claims, expires_in: f"{claims['type']}-token",
        )

        response = await service.refresh("refresh-token")

        service.session_repository.get_active_user_id_by_token_hash.assert_awaited_once()
        service.session_repository.create_session.assert_awaited_once()
        service.session_repository.rotate_refresh_session.assert_awaited_once()
        self.assertEqual(response.access_token, "access-token")
        self.assertEqual(response.refresh_token, "refresh-token")

    async def test_refresh_rejects_cached_subject_mismatch(self) -> None:
        service = AuthService(SimpleNamespace())
        service.session_repository = SimpleNamespace(
            get_active_user_id_by_token_hash=AsyncMock(return_value=7),
        )
        service.user_repository = SimpleNamespace(get_by_id=AsyncMock())
        service.token_signer = SimpleNamespace(
            verify=lambda token: {"type": "refresh", "sub": "42"},
        )

        with self.assertRaises(AppError):
            await service.refresh("refresh-token")

        service.user_repository.get_by_id.assert_not_awaited()

    async def test_verify_code_invalidates_account_caches_when_profile_fields_change(self) -> None:
        session = SimpleNamespace(info={})
        service = AuthService(session)
        user = SimpleNamespace(
            id=42,
            email="user@example.com",
            name="QA User",
            plan="pro",
            locale="zh-TW",
            timezone="Asia/Taipei",
            is_active=True,
        )
        service.policy = SimpleNamespace(is_new_user=lambda current_user: False)
        service.email_code_repository = SimpleNamespace(
            find_valid_code=AsyncMock(return_value=SimpleNamespace(id=7)),
            mark_used=AsyncMock(),
        )
        service.user_repository = SimpleNamespace(
            get_by_email=AsyncMock(return_value=user),
            upsert_by_email=AsyncMock(return_value=user),
            update_last_login=AsyncMock(),
        )
        service.session_repository = SimpleNamespace(
            create_session=AsyncMock(),
        )
        service.token_signer = SimpleNamespace(
            sign=lambda user_id, claims, expires_in: f"{claims['type']}-token",
        )

        with (
            patch(
                "domains.auth.service.schedule_invalidate_account_dashboard"
            ) as dashboard_invalidator,
            patch(
                "domains.auth.service.schedule_invalidate_account_profile"
            ) as profile_invalidator,
        ):
            response = await service.verify_code(
                "user@example.com",
                "123456",
                locale="zh-TW",
                timezone_name="Asia/Taipei",
            )

        service.user_repository.update_last_login.assert_awaited_once_with(
            42,
            "zh-TW",
            "Asia/Taipei",
        )
        dashboard_invalidator.assert_called_once_with(session, 42)
        profile_invalidator.assert_called_once_with(session, 42)
        self.assertEqual(response.user.locale, "zh-TW")
        self.assertEqual(response.user.timezone, "Asia/Taipei")


if __name__ == "__main__":
    unittest.main()
