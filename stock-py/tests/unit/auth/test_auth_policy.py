import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from domains.auth.policies import AuthPolicy


class AuthPolicyTest(unittest.TestCase):
    def test_is_new_user_when_first_login_matches_creation_time(self) -> None:
        now = datetime.now(timezone.utc)
        user = SimpleNamespace(
            created_at=now,
            last_login_at=now + timedelta(seconds=2),
        )

        self.assertTrue(AuthPolicy().is_new_user(user))

    def test_is_new_user_returns_false_for_old_account(self) -> None:
        now = datetime.now(timezone.utc)
        user = SimpleNamespace(
            created_at=now - timedelta(days=3),
            last_login_at=now,
        )

        self.assertFalse(AuthPolicy().is_new_user(user))


if __name__ == "__main__":
    unittest.main()
