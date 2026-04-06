"""
Password reset service for secure password recovery flow.
"""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from domains.auth.user import User
from infra.cache import cache
from infra.security import hash_password, verify_password


# Redis key helpers
def password_reset_key(email: str) -> str:
    return f"password_reset:{email}"


def password_reset_attempts_key(email: str) -> str:
    return f"password_reset_attempts:{email}"


class PasswordResetService:
    """Service for password reset functionality."""

    # Configuration
    RESET_CODE_EXPIRY_MINUTES = 15
    MAX_RESET_ATTEMPTS = 5
    RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour

    def __init__(self, db: AsyncSession):
        self.db = db

    async def request_password_reset(self, email: str) -> str:
        """
        Initiate password reset for a given email.
        Returns the reset code (in production, send via email).
        Raises ValueError if user not found or rate limited.
        """
        # Check rate limit
        await self._check_rate_limit(email)

        # Find user
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        
        if not user:
            # Don't reveal whether email exists
            # But still process to prevent enumeration
            return "reset_sent"  # type: ignore

        # Generate secure reset code
        reset_code = self._generate_secure_code()
        
        # Store in database
        user.reset_code = reset_code
        user.reset_code_expires = datetime.utcnow() + timedelta(
            minutes=self.RESET_CODE_EXPIRY_MINUTES
        )
        await self.db.commit()

        # Cache the reset token for faster lookup
        await cache.set(
            password_reset_key(email),
            {"code": reset_code, "user_id": user.id},
            expire=self.RESET_CODE_EXPIRY_MINUTES * 60,
        )

        # Increment attempt counter
        await self._increment_attempts(email)

        return reset_code

    async def verify_reset_code(self, email: str, code: str) -> bool:
        """
        Verify the password reset code.
        Returns True if valid, False otherwise.
        """
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            return False

        # Check code validity
        if (
            not user.reset_code
            or user.reset_code != code
            or not user.reset_code_expires
            or user.reset_code_expires < datetime.utcnow()
        ):
            return False

        return True

    async def reset_password(self, email: str, code: str, new_password: str) -> bool:
        """
        Reset user's password with verification code.
        Returns True if successful, raises ValueError if invalid.
        """
        # Verify code first
        if not await self.verify_reset_code(email, code):
            raise ValueError("Invalid or expired reset code")

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Validate password strength
        self._validate_password_strength(new_password)

        # Update password
        user.hashed_password = hash_password(new_password)
        user.reset_code = None
        user.reset_code_expires = None
        await self.db.commit()

        # Clear cached reset token
        await cache.delete(password_reset_key(email))

        # TODO: Invalidate all user sessions (require re-login)
        # This would require iterating through session keys

        return True

    async def cancel_password_reset(self, email: str) -> None:
        """Cancel an ongoing password reset request."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.reset_code = None
            user.reset_code_expires = None
            await self.db.commit()

        await cache.delete(password_reset_key(email))

    # Helper methods

    def _generate_secure_code(self) -> str:
        """Generate a cryptographically secure reset code."""
        return secrets.token_hex(3).upper()  # 6 characters

    def _validate_password_strength(self, password: str) -> None:
        """Validate password meets minimum requirements."""
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")
        
        # Check for mixed case
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        strength_score = sum([has_upper, has_lower, has_digit])
        if strength_score < 2:
            raise ValueError(
                "Password must contain at least 2 of: uppercase, lowercase, digits"
            )

    async def _check_rate_limit(self, email: str) -> None:
        """Check if user has exceeded password reset attempt limit."""
        key = password_reset_attempts_key(email)
        attempts = await cache.get(key)
        
        if attempts and attempts.get("count", 0) >= self.MAX_RESET_ATTEMPTS:
            raise ValueError(
                f"Too many reset attempts. Please try again in "
                f"{self.RATE_LIMIT_WINDOW_SECONDS // 60} minutes."
            )

    async def _increment_attempts(self, email: str) -> None:
        """Increment password reset attempt counter."""
        key = password_reset_attempts_key(email)
        current = await cache.get(key) or {}
        count = current.get("count", 0) + 1
        
        await cache.set(key, {"count": count}, expire=self.RATE_LIMIT_WINDOW_SECONDS)

    async def cleanup_expired_codes(self) -> int:
        """Clean up expired reset codes from database. Returns count cleaned."""
        from sqlalchemy import and_
        
        result = await self.db.execute(
            select(User).where(
                and_(
                    User.reset_code.isnot(None),
                    User.reset_code_expires < datetime.utcnow()
                )
            )
        )
        users = result.scalars().all()
        
        count = 0
        for user in users:
            user.reset_code = None
            user.reset_code_expires = None
            count += 1
        
        if count > 0:
            await self.db.commit()
        
        return count