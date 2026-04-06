"""
Audit log model for tracking admin actions.
"""
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from infra.database import Base


class AuditAction(str, Enum):
    """Audit action types."""
    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    STRATEGY_CREATE = "strategy.create"
    STRATEGY_UPDATE = "strategy.update"
    STRATEGY_DELETE = "strategy.delete"
    STRATEGY_ENABLE = "strategy.enable"
    STRATEGY_DISABLE = "strategy.disable"
    DISTRIBUTION_CREATE = "distribution.create"
    DISTRIBUTION_UPDATE = "distribution.update"
    DISTRIBUTION_DELETE = "distribution.delete"
    SETTINGS_CHANGE = "settings.change"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"
    SYSTEM_CONFIG = "system.config"
    MANUAL_TRADE = "manual.trade"


class AuditLog(Base):
    """Audit log model for tracking admin operations."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(50), nullable=True)
    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True, nullable=False
    )

    __table_args__ = (
        Index("ix_audit_logs_admin_action", "admin_user_id", "action"),
        Index("ix_audit_logs_created_action", "created_at", "action"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, username={self.username})>"


# Type alias for audit action strings
AuditActionType = str