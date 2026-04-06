"""
User model with extended authentication fields.
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class User(Base):
    """User model for authentication and profile."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Email verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verification_code: Mapped[str] = mapped_column(String(6), nullable=True)
    verification_expires: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Password reset
    reset_code: Mapped[str] = mapped_column(String(6), nullable=True)
    reset_code_expires: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    
    # Two-factor authentication
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    two_factor_secret: Mapped[str] = mapped_column(String(255), nullable=True)
    two_factor_backup_codes: Mapped[str] = mapped_column(String(255), nullable=True)
    
    # Session tracking
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    last_ip: Mapped[str] = mapped_column(String(45), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )