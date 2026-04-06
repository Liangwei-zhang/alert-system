"""
Authentication service: user management, sessions, rate limiting.
"""
import ipaddress
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.cache import cache
from infra.config import settings
from infra.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_code,
    hash_password,
    verify_password,
    verify_token_type,
)
from domains.auth.user import User


# Redis keys
def rate_limit_key(ip: str) -> str:
    return f"rate_limit:{ip}"


def session_key(token: str) -> str:
    return f"session:{token}"


def verification_code_key(email: str, code_type: str) -> str:
    return f"verify:{code_type}:{email}"


class AuthService:
    """Authentication service with session and rate limit management."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        ip: Optional[str] = None,
    ) -> User:
        """Register a new user."""
        # Check existing
        result = await self.db.execute(
            select(User).where(
                (User.username == username) | (User.email == email)
            )
        )
        if result.scalar_one_or_none():
            raise ValueError("Username or email already exists")

        # Create user
        user = User(
            username=username,
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            last_ip=ip,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(
        self,
        email: str,
        password: str,
        ip: Optional[str] = None,
    ) -> dict:
        """Login user, returns tokens and user info."""
        # Check rate limit
        if ip:
            await self._check_rate_limit(ip)

        # Find user
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user or not verify_password(password, user.hashed_password):
            raise ValueError("Invalid email or password")

        if not user.is_active:
            raise ValueError("Account is disabled")

        # Update last login
        user.last_login = datetime.utcnow()
        user.last_ip = ip
        await self.db.commit()

        # Create tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store session
        await self._create_session(access_token, user.id, ip)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def login_with_verification_code(
        self,
        email: str,
        code: str,
        ip: Optional[str] = None,
    ) -> dict:
        """Login with email verification code."""
        if ip:
            await self._check_rate_limit(ip)

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("User not found")

        # Verify code
        if (
            not user.verification_code
            or user.verification_code != code
            or not user.verification_expires
            or user.verification_expires < datetime.utcnow()
        ):
            raise ValueError("Invalid or expired verification code")

        # Clear code
        user.verification_code = None
        user.verification_expires = None
        user.email_verified = True
        user.last_login = datetime.utcnow()
        user.last_ip = ip
        await self.db.commit()

        # Create tokens
        token_data = {"sub": str(user.id), "email": user.email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        await self._create_session(access_token, user.id, ip)

        return {
            "user": user,
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    async def send_verification_code(self, email: str) -> str:
        """Generate and store verification code (returns code for testing)."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("User not found")

        code = generate_verification_code()
        user.verification_code = code
        user.verification_expires = datetime.utcnow() + timedelta(minutes=10)
        await self.db.commit()

        return code  # In production, send via email

    async def verify_email(self, email: str, code: str) -> bool:
        """Verify email with code."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            return False

        if (
            user.verification_code == code
            and user.verification_expires
            and user.verification_expires > datetime.utcnow()
        ):
            user.email_verified = True
            user.verification_code = None
            user.verification_expires = None
            await self.db.commit()
            return True
        return False

    async def refresh_tokens(self, refresh_token: str) -> dict:
        """Refresh access token using refresh token."""
        payload = verify_token_type(refresh_token, "refresh")
        user_id = int(payload.get("sub"))

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise ValueError("Invalid user")

        # Create new tokens
        token_data = {"sub": str(user.id), "email": user.email}
        new_access = create_access_token(token_data)
        new_refresh = create_refresh_token(token_data)

        await self._create_session(new_access, user.id, user.last_ip)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
        }

    async def logout(self, access_token: str) -> None:
        """Invalidate session."""
        await self._delete_session(access_token)

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    # Session management
    async def _create_session(
        self, token: str, user_id: int, ip: Optional[str]
    ) -> None:
        """Store session in Redis."""
        session_data = {
            "user_id": user_id,
            "ip": ip,
            "created_at": datetime.utcnow().isoformat(),
        }
        await cache.set(session_key(token), session_data, expire=1800)  # 30 min

    async def _delete_session(self, token: str) -> None:
        """Delete session from Redis."""
        await cache.delete(session_key(token))

    async def validate_session(self, token: str) -> Optional[dict]:
        """Validate session exists."""
        return await cache.get(session_key(token))

    # Rate limiting
    async def _check_rate_limit(self, ip: str) -> None:
        """Check rate limit for IP."""
        key = rate_limit_key(ip)
        count = await cache.incr(key)
        if count == 1:
            # Set expiry on first request
            await cache.client.expire(key, 60)  # type: ignore
        if count > settings.RATE_LIMIT_PER_MINUTE:
            raise ValueError("Rate limit exceeded. Try again later.")