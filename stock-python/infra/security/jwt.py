"""
Security utilities: password hashing and JWT tokens.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer

from infra.config import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return pyjwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create JWT refresh token (longer expiry)."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    return pyjwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate JWT token."""
    try:
        payload = pyjwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except Exception as e:
        raise ValueError(f"Invalid token: {e}")


def verify_token(token: str) -> dict:
    """Verify and decode token."""

def verify_token_type(token: str, expected_type: str) -> dict:
    """Decode token and verify its type."""
    payload = decode_token(token)
    if payload.get("type") != expected_type:
        raise ValueError(f"Invalid token type: expected {expected_type}")
    return payload


def generate_verification_code(length: int = 6) -> str:
    """Generate a numeric verification code."""
    return "".join([str(secrets.randbelow(10)) for _ in range(length)])


def get_current_user_optional(token: Optional[str] = None) -> Optional["User"]:
    """Get current user from token if provided, otherwise return None."""
    if not token:
        return None
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        # Import here to avoid circular imports
        from infra.database import get_db
        from domains.auth.user import User
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        return user
    except Exception:
        return None


def get_current_user(
    token: str = Depends(HTTPBearer)
) -> "User":
    """Get current authenticated user from JWT token."""
    from fastapi import HTTPException, Depends as FastAPIDepends
    from fastapi.security import HTTPBearer
    from infra.database import get_db
    from domains.auth.user import User
    
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        db = next(get_db())
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="User is inactive")
        return user
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))