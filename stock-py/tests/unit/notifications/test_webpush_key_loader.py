import base64
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from infra.security.webpush import load_vapid_private_key


def _public_key_base64url(private_key: ec.EllipticCurvePrivateKey) -> str:
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(public_bytes).decode("utf-8").rstrip("=")


class WebPushKeyLoaderTest(unittest.TestCase):
    def test_load_vapid_private_key_accepts_pem(self) -> None:
        private_key = ec.generate_private_key(ec.SECP256R1())
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")

        loaded = load_vapid_private_key(private_pem)

        self.assertEqual(
            _public_key_base64url(loaded.private_key),
            _public_key_base64url(private_key),
        )


if __name__ == "__main__":
    unittest.main()