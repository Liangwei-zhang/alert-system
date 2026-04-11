import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from infra.security.token_signer import TokenSigner


class TokenSignerTest(unittest.TestCase):
    def test_sign_issues_distinct_tokens_within_same_second(self) -> None:
        signer = TokenSigner(secret_key="test-secret", algorithm="HS256", default_ttl_minutes=30)
        fixed_now = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=5)

        with patch("infra.security.token_signer.datetime") as mocked_datetime:
            mocked_datetime.now.return_value = fixed_now
            first_token = signer.sign(7, claims={"type": "access"}, expires_in=timedelta(minutes=30))
            second_token = signer.sign(7, claims={"type": "access"}, expires_in=timedelta(minutes=30))

        first_payload = signer.verify(first_token)
        second_payload = signer.verify(second_token)

        self.assertNotEqual(first_token, second_token)
        self.assertEqual(first_payload["iat"], second_payload["iat"])
        self.assertEqual(first_payload["exp"], second_payload["exp"])
        self.assertIn("jti", first_payload)
        self.assertIn("jti", second_payload)
        self.assertNotEqual(first_payload["jti"], second_payload["jti"])


if __name__ == "__main__":
    unittest.main()