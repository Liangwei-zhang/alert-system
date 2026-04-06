from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infra.cache.redis_client import get_redis
from infra.core.config import get_settings
from infra.db.models.account import UserAccountModel
from infra.db.models.auth import EmailCodeModel, SessionModel, UserModel
from infra.observability.metrics import get_metrics_registry
from infra.security.session_cache import (
    cache_active_session,
    get_cached_session_user_id,
    schedule_cache_session,
    schedule_invalidate_sessions,
)

logger = logging.getLogger(__name__)
metrics = get_metrics_registry()

_EMAIL_CODE_CLEANUP_LEASE_KEY = "auth:email-codes:cleanup:lease"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_admin_users(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        query: str | None = None,
        plan: str | None = None,
        is_active: bool | None = None,
    ) -> list[tuple[UserModel, UserAccountModel | None]]:
        statement = select(UserModel, UserAccountModel).outerjoin(
            UserAccountModel,
            UserAccountModel.user_id == UserModel.id,
        )
        filters = self._admin_user_filters(query=query, plan=plan, is_active=is_active)
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(
            statement.order_by(UserModel.created_at.desc(), UserModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return [(user, account) for user, account in result.all()]

    async def count_admin_users(
        self,
        *,
        query: str | None = None,
        plan: str | None = None,
        is_active: bool | None = None,
    ) -> int:
        statement = select(func.count()).select_from(UserModel)
        filters = self._admin_user_filters(query=query, plan=plan, is_active=is_active)
        if filters:
            statement = statement.where(*filters)
        result = await self.session.execute(statement)
        return int(result.scalar_one() or 0)

    async def get_admin_user_detail(
        self, user_id: int
    ) -> tuple[UserModel | None, UserAccountModel | None]:
        result = await self.session.execute(
            select(UserModel, UserAccountModel)
            .outerjoin(UserAccountModel, UserAccountModel.user_id == UserModel.id)
            .where(UserModel.id == user_id)
        )
        row = result.one_or_none()
        if row is None:
            return None, None
        return row[0], row[1]

    async def list_admin_users_by_ids(
        self, user_ids: list[int]
    ) -> list[tuple[UserModel, UserAccountModel | None]]:
        return await self.list_users_by_ids(user_ids)

    async def list_users_by_ids(
        self, user_ids: list[int]
    ) -> list[tuple[UserModel, UserAccountModel | None]]:
        resolved_ids = [int(user_id) for user_id in user_ids if int(user_id) > 0]
        if not resolved_ids:
            return []
        result = await self.session.execute(
            select(UserModel, UserAccountModel)
            .outerjoin(UserAccountModel, UserAccountModel.user_id == UserModel.id)
            .where(UserModel.id.in_(resolved_ids))
        )
        rows = {(user.id): (user, account) for user, account in result.all()}
        return [rows[user_id] for user_id in resolved_ids if user_id in rows]

    async def get_by_email(self, email: str) -> UserModel | None:
        result = await self.session.execute(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> UserModel | None:
        result = await self.session.execute(select(UserModel).where(UserModel.id == user_id))
        return result.scalar_one_or_none()

    async def upsert_by_email(
        self,
        email: str,
        locale: str | None = None,
        timezone_name: str | None = None,
    ) -> UserModel:
        normalized_email = email.strip().lower()
        existing = await self.get_by_email(normalized_email)
        if existing is not None:
            existing.last_login_at = utcnow()
            if locale:
                existing.locale = locale
            if timezone_name:
                existing.timezone = timezone_name
            await self.session.flush()
            return existing

        user = UserModel(
            email=normalized_email,
            locale=locale or "zh-CN",
            timezone=timezone_name or "Asia/Shanghai",
            extra={
                "subscription": {
                    "status": "draft",
                    "started_at": None,
                    "last_synced_at": None,
                    "last_sync_reason": None,
                }
            },
            last_login_at=utcnow(),
        )
        self.session.add(user)
        await self.session.flush()

        self.session.add(
            UserAccountModel(
                user_id=user.id,
                total_capital=0,
                currency="USD",
            )
        )
        await self.session.flush()
        return user

    async def update_admin_user(
        self,
        user_id: int,
        *,
        name: str | None = None,
        plan: str | None = None,
        locale: str | None = None,
        timezone_name: str | None = None,
        is_active: bool | None = None,
        extra: dict[str, Any] | None = None,
    ) -> UserModel | None:
        user = await self.session.get(UserModel, user_id)
        if user is None:
            return None
        if name is not None:
            user.name = name
        if plan is not None:
            user.plan = plan
        if locale is not None:
            user.locale = locale
        if timezone_name is not None:
            user.timezone = timezone_name
        if is_active is not None:
            user.is_active = is_active
        if extra is not None:
            payload = dict(user.extra or {})
            payload.update(extra)
            user.extra = payload
        await self.session.flush()
        return user

    async def bulk_update_admin_users(
        self,
        user_ids: list[int],
        *,
        plan: str | None = None,
        is_active: bool | None = None,
    ) -> list[int]:
        resolved_ids = sorted({int(user_id) for user_id in user_ids if int(user_id) > 0})
        if not resolved_ids:
            return []
        values: dict[str, Any] = {}
        if plan is not None:
            values["plan"] = plan
        if is_active is not None:
            values["is_active"] = is_active
        if values:
            await self.session.execute(
                update(UserModel).where(UserModel.id.in_(resolved_ids)).values(**values)
            )
            await self.session.flush()
        return resolved_ids

    async def update_last_login(
        self,
        user_id: int,
        locale: str | None = None,
        timezone_name: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"last_login_at": utcnow()}
        if locale:
            values["locale"] = locale
        if timezone_name:
            values["timezone"] = timezone_name

        await self.session.execute(
            update(UserModel).where(UserModel.id == user_id).values(**values)
        )
        await self.session.flush()

    @staticmethod
    def _admin_user_filters(
        *,
        query: str | None = None,
        plan: str | None = None,
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
        if plan:
            filters.append(UserModel.plan == plan.strip().lower())
        if is_active is not None:
            filters.append(UserModel.is_active.is_(is_active))
        return filters


class EmailCodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_code(
        self,
        email: str,
        code: str,
        ip: str | None,
        expires_at: datetime,
    ) -> EmailCodeModel:
        model = EmailCodeModel(
            email=email.strip().lower(),
            code=code,
            ip=ip,
            expires_at=expires_at,
        )
        self.session.add(model)
        await self.session.flush()
        return model

    async def find_valid_code(self, email: str, code: str) -> EmailCodeModel | None:
        result = await self.session.execute(
            select(EmailCodeModel)
            .where(
                EmailCodeModel.email == email.strip().lower(),
                EmailCodeModel.code == code,
                EmailCodeModel.used_at.is_(None),
                EmailCodeModel.expires_at > utcnow(),
            )
            .order_by(EmailCodeModel.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_used(self, code_id: int) -> None:
        await self.session.execute(
            update(EmailCodeModel).where(EmailCodeModel.id == code_id).values(used_at=utcnow())
        )
        await self.session.flush()

    async def delete_expired(self) -> None:
        await self.session.execute(
            delete(EmailCodeModel).where(EmailCodeModel.expires_at < utcnow())
        )
        await self.session.flush()

    async def delete_expired_if_due(self, interval_seconds: int | None = None) -> bool:
        if interval_seconds is None:
            interval_seconds = get_settings().email_code_cleanup_interval_seconds

        if interval_seconds <= 0:
            await self.delete_expired()
            metrics.counter(
                "auth_email_code_cleanup_runs_total",
                "Inline email code cleanup runs",
            ).inc()
            return True

        try:
            client = await get_redis()
            acquired = await client.set(
                _EMAIL_CODE_CLEANUP_LEASE_KEY,
                "1",
                ex=interval_seconds,
                nx=True,
            )
        except Exception:
            logger.warning("Email code cleanup lease acquisition failed", exc_info=True)
            metrics.counter(
                "auth_email_code_cleanup_lease_failures_total",
                "Failed attempts to acquire the email code cleanup lease",
            ).inc()
            return False

        if not acquired:
            metrics.counter(
                "auth_email_code_cleanup_skipped_total",
                "Skipped email code cleanup runs because another worker owns the lease",
            ).inc()
            return False

        await self.delete_expired()
        metrics.counter(
            "auth_email_code_cleanup_runs_total",
            "Email code cleanup runs",
        ).inc()
        return True


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_active_user_id_by_token_hash(self, token_hash: str) -> int | None:
        cached_user_id = await get_cached_session_user_id(token_hash)
        if cached_user_id is not None:
            metrics.counter(
                "auth_refresh_session_cache_hits_total",
                "Refresh session cache hits",
            ).inc()
            return cached_user_id

        metrics.counter(
            "auth_refresh_session_cache_misses_total",
            "Refresh session cache misses",
        ).inc()

        result = await self.session.execute(
            select(SessionModel).where(
                SessionModel.token_hash == token_hash,
                SessionModel.expires_at > utcnow(),
            )
        )
        session_record = result.scalar_one_or_none()
        if session_record is None:
            return None

        await cache_active_session(token_hash, session_record.user_id, session_record.expires_at)
        return int(session_record.user_id)

    async def create_session(
        self,
        token_hash: str,
        user_id: int,
        expires_at: datetime,
        device_info: dict[str, Any] | None = None,
    ) -> SessionModel:
        model = SessionModel(
            token_hash=token_hash,
            user_id=user_id,
            device_info=device_info or {},
            expires_at=expires_at,
        )
        self.session.add(model)
        await self.session.flush()
        schedule_cache_session(self.session, token_hash, user_id, expires_at)
        return model

    async def get_active_by_token_hash(self, token_hash: str) -> SessionModel | None:
        result = await self.session.execute(
            select(SessionModel).where(
                SessionModel.token_hash == token_hash,
                SessionModel.expires_at > utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def revoke_by_token_hash(self, token_hash: str) -> None:
        await self.session.execute(
            delete(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        await self.session.flush()
        schedule_invalidate_sessions(self.session, [token_hash])

    async def revoke_for_user(self, user_id: int) -> None:
        result = await self.session.execute(
            select(SessionModel.token_hash).where(SessionModel.user_id == user_id)
        )
        token_hashes = list(result.scalars().all())
        await self.session.execute(delete(SessionModel).where(SessionModel.user_id == user_id))
        await self.session.flush()
        schedule_invalidate_sessions(self.session, token_hashes)

    async def rotate_refresh_session(
        self,
        old_token_hash: str,
        new_token_hash: str,
        user_id: int,
        expires_at: datetime,
        device_info: dict[str, Any] | None = None,
    ) -> SessionModel:
        await self.revoke_by_token_hash(old_token_hash)
        return await self.create_session(
            token_hash=new_token_hash,
            user_id=user_id,
            expires_at=expires_at,
            device_info=device_info,
        )
