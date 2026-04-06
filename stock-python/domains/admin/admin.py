"""
Admin user model with role-based access control.
"""
from datetime import datetime

from sqlalchemy import String, DateTime, Integer, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from infra.database import Base


class AdminRole(str, enum.Enum):
    """Admin role enumeration."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class AdminUser(Base):
    """Admin user model for system management."""

    __tablename__ = "admin_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(100), nullable=True)
    role: Mapped[AdminRole] = mapped_column(
        SQLEnum(AdminRole), default=AdminRole.VIEWER, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    last_login: Mapped[datetime] = mapped_column(DateTime, nullable=True)