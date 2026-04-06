from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from infra.db.models.base import Base, sql_enum


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdminOperatorRole(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class AdminOperatorModel(Base):
    __tablename__ = "admin_operators"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[AdminOperatorRole] = mapped_column(
        sql_enum(AdminOperatorRole, name="admin_operator_role"),
        nullable=False,
        default=AdminOperatorRole.OPERATOR,
        server_default=AdminOperatorRole.OPERATOR.value,
        index=True,
    )
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_action_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utcnow,
        onupdate=utcnow,
        server_default=func.now(),
    )


__all__ = ["AdminOperatorModel", "AdminOperatorRole"]
