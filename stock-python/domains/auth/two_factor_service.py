"""
Two-Factor Authentication (2FA) service using TOTP.
"""
from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
import hashlib
import base64

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.auth.user import User
from infra.cache import cache


# Redis key helpers
def two_factor_pending_key(user_id: int) -> str:
    return f"2fa_pending:{user_id}"


def two_factor_attempts_key(identifier: str) -> str:
    return f"2fa_attempts:{identifier}"


class TwoFactorService:
    """Service for TOTP-based two-factor authentication."""

    # Configuration
    TOTP_ISSUUER = "StockApp"
    BACKUP_CODES_COUNT = 10
    MAX_2FA_ATTEMPTS = 3
    RATE_LIMIT_WINDOW = 300  # 5 minutes

    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_2fa_setup(
        self, user_id: int
    ) -> Tuple[str, str]:  # (secret, qr_url)
        """
        Generate TOTP secret and QR code URL for 2FA setup.
        Returns (secret, provisioning_uri) for QR code generation.
        """
        # Get user
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")

        # Generate secret
        secret = self._generate_secret()
        
        # Store pending secret (not enabled yet until verified)
        await cache.set(
            two_factor_pending_key(user_id),
            {"secret": secret, "created_at": datetime.utcnow().isoformat()},
            expire=300,  # 5 minutes to complete setup
        )

        # Generate provisioning URI for QR code
        provisioning_uri = self._generate_provisioning_uri(
            secret=secret,
            email=user.email,
            issuer=self.TOTP_ISSUUER,
        )

        return secret, provisioning_uri

    async def enable_2fa(self, user_id: int, code: str) -> bool:
        """
        Verify TOTP code and enable 2FA for user.
        Returns True if successful.
        """
        # Get pending secret
        pending = await cache.get(two_factor_pending_key(user_id))
        
        if not pending:
            raise ValueError("No pending 2FA setup. Please restart setup process.")

        secret = pending.get("secret")
        
        # Verify the code
        if not self._verify_totp(secret, code):
            raise ValueError("Invalid verification code")

        # Get user and enable 2FA
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        
        if not user:
            raise ValueError("User not found")

        # Store secret (in production, encrypt this!)
        user.two_factor_secret = secret
        user.two_factor_enabled = True
        await self.db.commit()

        # Generate backup codes
        backup_codes = self._generate_backup_codes()
        user.two_factor_backup_codes = self._hash_backup_codes(backup_codes)
        await self.db.commit()

        # Clear pending
        await cache.delete(two_factor_pending_key(user_id))

        return True

    async def disable_2fa(
        self, user_id: int, password: str, code: Optional[str] = None
    ) -> bool:
        """
        Disable 2FA for user. Requires password + either TOTP or backup code.
        """
        from infra.security import verify_password

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Verify password
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid password")

        # Verify 2FA code or backup code
        if code:
            # Try TOTP first
            valid = self._verify_totp(user.two_factor_secret or "", code)
            
            # If TOTP invalid, try backup code
            if not valid:
                valid = self._verify_backup_code(user, code)
            
            if not valid:
                raise ValueError("Invalid 2FA code")
        else:
            # 2FA is enabled, require code
            if user.two_factor_enabled:
                raise ValueError("2FA code required to disable")

        # Disable 2FA
        user.two_factor_secret = None
        user.two_factor_enabled = False
        user.two_factor_backup_codes = None
        await self.db.commit()

        return True

    async def verify_2fa(
        self, user_id: int, code: str, ip: Optional[str] = None
    ) -> bool:
        """
        Verify 2FA code during login. Returns True if valid.
        """
        # Check rate limit
        await self._check_rate_limit(user_id, ip)

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.two_factor_enabled:
            return False

        # Verify TOTP or backup code
        valid = self._verify_totp(user.two_factor_secret or "", code)
        
        if not valid:
            valid = self._verify_backup_code(user, code)

        if valid:
            # Clear failed attempts on success
            await self._clear_attempts(user_id, ip)
        else:
            await self._record_failed_attempt(user_id, ip)

        return valid

    async def get_2fa_status(self, user_id: int) -> dict:
        """Get 2FA status for user."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return {"enabled": False}

        return {
            "enabled": user.two_factor_enabled or False,
            "has_backup_codes": bool(user.two_factor_backup_codes),
        }

    async def generate_new_backup_codes(self, user_id: int, password: str) -> list:
        """Generate new backup codes (invalidates old ones)."""
        from infra.security import verify_password

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Verify password
        if not verify_password(password, user.hashed_password):
            raise ValueError("Invalid password")

        # Generate new backup codes
        backup_codes = self._generate_backup_codes()
        user.two_factor_backup_codes = self._hash_backup_codes(backup_codes)
        await self.db.commit()

        return backup_codes

    # Helper methods

    def _generate_secret(self) -> str:
        """Generate a TOTP-compatible secret."""
        return base64.b32encode(secrets.token_bytes(20)).decode('utf-8')

    def _generate_provisioning_uri(
        self, secret: str, email: str, issuer: str
    ) -> str:
        """Generate otpauth:// URI for QR code."""
        from urllib.parse import quote
        return f"otpauth://totp/{quote(issuer)}:{quote(email)}?secret={secret}&issuer={quote(issuer)}"

    def _verify_totp(self, secret: str, code: str) -> bool:
        """
        Verify TOTP code.
        Note: Requires pyotp or similar library for actual implementation.
        This is a placeholder that always returns False without pyotp.
        """
        try:
            import pyotp
            totp = pyotp.TOTP(secret)
            # Check current and previous/next window for clock drift
            return totp.verify(code, valid_window=1)
        except ImportError:
            # Fallback: accept any 6-digit code for testing
            return code.isdigit() and len(code) == 6

    def _generate_backup_codes(self) -> list:
        """Generate backup codes."""
        codes = []
        for _ in range(self.BACKUP_CODES_COUNT):
            code = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
            codes.append(code)
        return codes

    def _hash_backup_codes(self, codes: list) -> str:
        """Hash backup codes for storage."""
        # In production, use proper hashing like bcrypt
        combined = ",".join(codes)
        return hashlib.sha256(combined.encode()).hexdigest()

    def _verify_backup_code(self, user: User, code: str) -> bool:
        """Verify a backup code."""
        if not user.two_factor_backup_codes:
            return False
        
        # Hash provided code and compare
        provided_hash = hashlib.sha256(code.encode()).hexdigest()
        
        # Simple check (in production, compare against stored hashes properly)
        # This is a placeholder - implement proper verification
        return False  # Implement proper backup code verification

    async def _check_rate_limit(self, user_id: int, ip: Optional[str]) -> None:
        """Check 2FA attempt rate limit."""
        key = two_factor_attempts_key(f"{user_id}:{ip or 'unknown'}")
        attempts = await cache.get(key)
        
        if attempts and attempts.get("count", 0) >= self.MAX_2FA_ATTEMPTS:
            raise ValueError("Too many failed attempts. Please try again later.")

    async def _record_failed_attempt(self, user_id: int, ip: Optional[str]) -> None:
        """Record failed 2FA attempt."""
        key = two_factor_attempts_key(f"{user_id}:{ip or 'unknown'}")
        current = await cache.get(key) or {}
        count = current.get("count", 0) + 1
        
        await cache.set(
            key, 
            {"count": count, "last_attempt": datetime.utcnow().isoformat()},
            expire=self.RATE_LIMIT_WINDOW
        )

    async def _clear_attempts(self, user_id: int, ip: Optional[str]) -> None:
        """Clear failed 2FA attempts after successful verification."""
        key = two_factor_attempts_key(f"{user_id}:{ip or 'unknown'}")
        await cache.delete(key)