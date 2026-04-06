from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.admin import AdminOperatorModel, AdminOperatorRole
from infra.db.models.auth import UserModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_admin_operators(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> list[tuple[AdminOperatorModel, UserModel]]:
        statement = select(AdminOperatorModel, UserModel).join(
            UserModel,
            UserModel.id == AdminOperatorModel.user_id,
        )
        filters = self._operator_filters(query=query, role=role, is_active=is_active)
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(
            statement.order_by(
                AdminOperatorModel.updated_at.desc(), AdminOperatorModel.user_id.asc()
            )
            .limit(limit)
            .offset(offset)
        )
        return [(operator, user) for operator, user in result.all()]

    async def count_admin_operators(
        self,
        *,
        query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        statement = select(func.count(AdminOperatorModel.user_id)).select_from(AdminOperatorModel)
        statement = statement.join(UserModel, UserModel.id == AdminOperatorModel.user_id)
        filters = self._operator_filters(query=query, role=role, is_active=is_active)
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def get_operator(
        self, user_id: int
    ) -> tuple[AdminOperatorModel | None, UserModel | None]:
        result = await self.session.execute(
            select(AdminOperatorModel, UserModel)
            .join(UserModel, UserModel.id == AdminOperatorModel.user_id)
            .where(AdminOperatorModel.user_id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None, None
        return row[0], row[1]

    async def get_active_operator(
        self,
        user_id: int,
        *,
        allowed_roles: set[str] | None = None,
    ) -> tuple[AdminOperatorModel | None, UserModel | None]:
        operator, user = await self.get_operator(user_id)
        if operator is None or user is None:
            return None, None
        if not bool(operator.is_active):
            return None, None
        if allowed_roles is not None and str(operator.role.value) not in allowed_roles:
            return None, None
        return operator, user

    async def upsert_operator(
        self,
        user_id: int,
        *,
        role: str | None = None,
        scopes: list[str] | None = None,
        is_active: bool | None = None,
    ) -> tuple[AdminOperatorModel | None, UserModel | None]:
        user = await self.session.get(UserModel, user_id)
        if user is None:
            return None, None

        operator = await self.session.get(AdminOperatorModel, user_id)
        if operator is None:
            operator = AdminOperatorModel(user_id=user_id)
            self.session.add(operator)

        if role is not None:
            operator.role = AdminOperatorRole(str(role).strip().lower())
        if scopes is not None:
            operator.scopes = self._normalize_scopes(scopes)
        elif operator.scopes is None:
            operator.scopes = []
        if is_active is not None:
            operator.is_active = is_active
        operator.last_action_at = utcnow()
        await self.session.flush()
        return operator, user

    async def touch_operator(self, user_id: int) -> AdminOperatorModel | None:
        operator = await self.session.get(AdminOperatorModel, user_id)
        if operator is None:
            return None
        operator.last_action_at = utcnow()
        await self.session.flush()
        return operator

    @staticmethod
    def _normalize_scopes(scopes: list[str]) -> list[str]:
        normalized = {str(scope).strip().lower() for scope in scopes if str(scope).strip()}
        return sorted(normalized)

    @staticmethod
    def _operator_filters(
        *,
        query: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> list[Any]:
        filters: list[Any] = []
        if query:
            normalized = f"%{query.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(UserModel.email).like(normalized),
                    func.lower(func.coalesce(UserModel.name, "")).like(normalized),
                )
            )
        if role:
            filters.append(AdminOperatorModel.role == AdminOperatorRole(str(role).strip().lower()))
        if is_active is not None:
            filters.append(AdminOperatorModel.is_active.is_(is_active))
        return filters
