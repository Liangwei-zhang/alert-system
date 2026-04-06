"""
Trade link security - HMAC signing for public links.
"""

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from functools import lru_cache

# Default expiry for trade links (24 hours)
DEFAULT_LINK_EXPIRY_HOURS = 24


class TradeLinkSigner:
    """HMAC-based link security for trade confirmations."""

    def __init__(self, secret: str | None = None):
        """
        Initialize signer with secret key.

        Args:
            secret: Secret key for HMAC. Defaults to TRADE_LINK_SECRET from config.
        """
        if secret is None:
            from infra.core.config import get_settings

            secret = get_settings().trade_link_secret
        self.secret = secret

    def generate_token(self) -> str:
        """
        Generate a secure random token for the link.

        Returns:
            A cryptographically secure random token (hex-encoded).
        """
        return secrets.token_hex(32)

    def sign(self, token: str, user_id: int, symbol: str) -> str:
        """
        Generate HMAC signature for a trade link.

        Args:
            token: The link token.
            user_id: The user ID.
            symbol: The stock symbol.
        Returns:
            HMAC-SHA256 signature (hex-encoded).
        """
        message = f"{token}:{user_id}:{symbol.upper()}"

        signature = hmac.new(self.secret.encode(), message.encode(), hashlib.sha256).hexdigest()

        return signature

    def verify(self, token: str, user_id: int, symbol: str, signature: str) -> bool:
        """
        Verify a trade link signature using timing-safe comparison.

        Args:
            token: The link token.
            user_id: The user ID.
            symbol: The stock symbol.
            signature: The signature to verify.

        Returns:
            True if signature is valid, False otherwise.
        """
        # Generate expected signature
        expected = self.sign(token, user_id, symbol)

        # Use timing-safe comparison to prevent timing attacks
        return hmac.compare_digest(expected, signature)

    def verify_full(
        self, token: str, user_id: int, symbol: str, signature: str, expires_at: datetime
    ) -> bool:
        """
        Verify a full trade link (token + signature + expiry).

        Args:
            token: The link token.
            user_id: The user ID.
            symbol: The stock symbol.
            signature: The signature to verify.
            expires_at: Link expiration timestamp.

        Returns:
            True if all checks pass, False otherwise.
        """
        # Check expiration first (faster check)
        now = datetime.now(timezone.utc)
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if now > expires_at:
            return False

        # Verify signature
        return self.verify(token, user_id, symbol, signature)

    def create_link(
        self, user_id: int, symbol: str, expiry_hours: int = DEFAULT_LINK_EXPIRY_HOURS
    ) -> tuple[str, str, datetime]:
        """
        Create a complete trade link with token, signature, and expiry.

        Args:
            user_id: The user ID.
            symbol: The stock symbol.
            expiry_hours: Hours until link expires.

        Returns:
            Tuple of (token, signature, expires_at).
        """
        token = self.generate_token()
        signature = self.sign(token, user_id, symbol)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)

        return token, signature, expires_at


@lru_cache(maxsize=1)
def get_link_signer() -> TradeLinkSigner:
    return TradeLinkSigner()
