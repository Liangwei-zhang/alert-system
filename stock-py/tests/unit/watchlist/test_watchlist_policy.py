import unittest

from domains.watchlist.policies import WatchlistPolicy
from infra.core.errors import AppError


class WatchlistPolicyTest(unittest.TestCase):
    def test_normalize_symbol_trims_and_uppercases(self) -> None:
        policy = WatchlistPolicy()

        self.assertEqual(policy.normalize_symbol("  aapl "), "AAPL")

    def test_enforce_plan_limit_raises_when_full(self) -> None:
        policy = WatchlistPolicy()

        with self.assertRaises(AppError):
            policy.enforce_plan_limit("free", 5)


if __name__ == "__main__":
    unittest.main()
