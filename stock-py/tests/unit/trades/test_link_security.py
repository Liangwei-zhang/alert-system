import unittest
from datetime import datetime, timedelta, timezone

from domains.trades.link_security import TradeLinkSigner


class TradeLinkSignerTest(unittest.TestCase):
    def test_sign_and_verify_round_trip(self) -> None:
        signer = TradeLinkSigner(secret="test-secret")
        token = "token-123"

        signature = signer.sign(token=token, user_id=7, symbol="aapl")

        self.assertTrue(signer.verify(token=token, user_id=7, symbol="AAPL", signature=signature))

    def test_verify_rejects_mismatched_symbol(self) -> None:
        signer = TradeLinkSigner(secret="test-secret")
        signature = signer.sign(token="token-123", user_id=7, symbol="AAPL")

        self.assertFalse(
            signer.verify(token="token-123", user_id=7, symbol="MSFT", signature=signature)
        )

    def test_verify_full_rejects_expired_link(self) -> None:
        signer = TradeLinkSigner(secret="test-secret")
        signature = signer.sign(token="token-123", user_id=7, symbol="AAPL")
        expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)

        self.assertFalse(
            signer.verify_full(
                token="token-123",
                user_id=7,
                symbol="AAPL",
                signature=signature,
                expires_at=expires_at,
            )
        )


if __name__ == "__main__":
    unittest.main()
