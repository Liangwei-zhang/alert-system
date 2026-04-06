import unittest

from domains.subscription.policies import SubscriptionPolicy
from infra.core.errors import AppError


class SubscriptionPolicyTest(unittest.TestCase):
    def test_validate_start_request_requires_capital(self) -> None:
        policy = SubscriptionPolicy()

        with self.assertRaises(AppError):
            policy.validate_start_request(0, 1, 1, False)

    def test_build_state_sets_active_subscription(self) -> None:
        policy = SubscriptionPolicy()
        state = policy.build_state(
            extra={"subscription": {"status": "draft", "started_at": None}},
            snapshot={"currency": "USD"},
            summary={
                "watchlist_count": 2,
                "watchlist_notify_enabled": 1,
                "portfolio_count": 1,
                "push_device_count": 0,
            },
        )

        self.assertEqual(state["subscription"]["status"], "active")
        self.assertEqual(state["subscription"]["snapshot"]["watchlist_count"], 2)


if __name__ == "__main__":
    unittest.main()
