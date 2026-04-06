from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from uuid import uuid4

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from infra.cache.account_dashboard_cache import (
    apply_account_dashboard_cache_operations,
    pop_pending_account_dashboard_cache_operations,
)
from infra.cache.account_profile_cache import (
    apply_account_profile_cache_operations,
    pop_pending_account_profile_cache_operations,
)
from infra.cache.push_devices_cache import (
    apply_push_devices_cache_operations,
    pop_pending_push_devices_cache_operations,
)
from infra.cache.trade_info_cache import (
    apply_trade_info_cache_operations,
    pop_pending_trade_info_cache_operations,
)
from infra.core.config import Settings, get_settings
from infra.security.session_cache import (
    apply_session_cache_operations,
    pop_pending_session_cache_operations,
)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def build_database_url(settings: Settings) -> str:
    database_url = str(settings.database_url)
    if settings.database_pool_mode != "pgbouncer":
        return database_url

    parsed = urlparse(database_url)
    query_params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query_params["prepared_statement_cache_size"] = "0"
    query_params.pop("statement_cache_size", None)
    return urlunparse(parsed._replace(query=urlencode(query_params)))


def build_connect_args(settings: Settings) -> dict[str, object]:
    if settings.database_pool_mode != "pgbouncer":
        return {}
    return {
        "statement_cache_size": 0,
        "prepared_statement_name_func": lambda: f"__asyncpg_{uuid4()}__",
    }


def build_engine(settings: Settings | None = None) -> AsyncEngine:
    global _engine

    if _engine is not None:
        return _engine

    app_settings = settings or get_settings()
    engine_kwargs: dict[str, object] = {
        "echo": app_settings.database_echo or app_settings.debug,
        "pool_pre_ping": True,
    }

    database_url = build_database_url(app_settings)
    connect_args = build_connect_args(app_settings)

    if app_settings.database_pool_mode == "pgbouncer":
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = connect_args
    elif not database_url.startswith("sqlite"):
        engine_kwargs["pool_size"] = 20
        engine_kwargs["max_overflow"] = 40

    _engine = create_async_engine(database_url, **engine_kwargs)
    return _engine


def build_session_factory(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    global _session_factory

    if _session_factory is not None:
        return _session_factory

    _session_factory = async_sessionmaker(
        build_engine(settings),
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _session_factory


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return build_session_factory()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = build_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
            await apply_session_cache_operations(pop_pending_session_cache_operations(session))
            await apply_account_dashboard_cache_operations(
                pop_pending_account_dashboard_cache_operations(session)
            )
            await apply_account_profile_cache_operations(
                pop_pending_account_profile_cache_operations(session)
            )
            await apply_push_devices_cache_operations(
                pop_pending_push_devices_cache_operations(session)
            )
            await apply_trade_info_cache_operations(
                pop_pending_trade_info_cache_operations(session)
            )
        except Exception:
            pop_pending_session_cache_operations(session)
            pop_pending_account_dashboard_cache_operations(session)
            pop_pending_account_profile_cache_operations(session)
            pop_pending_push_devices_cache_operations(session)
            pop_pending_trade_info_cache_operations(session)
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
