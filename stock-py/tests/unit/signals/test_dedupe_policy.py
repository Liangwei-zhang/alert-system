import unittest
from datetime import datetime, timedelta, timezone

from domains.signals.dedupe_policy import SignalDedupePolicy


class SignalDedupePolicyTest(unittest.TestCase):
    def test_build_dedupe_key_normalizes_components(self) -> None:
        policy = SignalDedupePolicy(cooldown_minutes=30)

        key = policy.build_dedupe_key(" aapl ", "BUY", " 30m Mean Reversion ", " Risk On ")

        self.assertEqual(key, "AAPL:buy:30m-mean-reversion:risk-on")

    def test_should_suppress_when_matching_key_within_window(self) -> None:
        policy = SignalDedupePolicy(cooldown_minutes=30)
        now = datetime.now(timezone.utc)

        self.assertTrue(
            policy.should_suppress(
                existing_generated_at=now - timedelta(minutes=10),
                existing_dedupe_key="AAPL:buy:1h:trend",
                candidate_dedupe_key="AAPL:buy:1h:trend",
                now=now,
            )
        )

    def test_should_not_suppress_outside_window_or_different_key(self) -> None:
        policy = SignalDedupePolicy(cooldown_minutes=30)
        now = datetime.now(timezone.utc)

        self.assertFalse(
            policy.should_suppress(
                existing_generated_at=now - timedelta(minutes=45),
                existing_dedupe_key="AAPL:buy:1h:trend",
                candidate_dedupe_key="AAPL:buy:1h:trend",
                now=now,
            )
        )
        self.assertFalse(
            policy.should_suppress(
                existing_generated_at=now - timedelta(minutes=5),
                existing_dedupe_key="AAPL:sell:1h:trend",
                candidate_dedupe_key="AAPL:buy:1h:trend",
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
