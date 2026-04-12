from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

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
from infra.security.session_cache import (
    apply_session_cache_operations,
    pop_pending_session_cache_operations,
)

PendingOperationPopper = Callable[[AsyncSession], Any]
PendingOperationApplier = Callable[[Any], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class CacheOperationHandler:
    name: str
    pop_pending_operations: PendingOperationPopper
    apply_operations: PendingOperationApplier


_CACHE_OPERATION_HANDLERS: list[CacheOperationHandler] = []


def register_cache_handler(
    *,
    name: str,
    pop_pending_operations: PendingOperationPopper,
    apply_operations: PendingOperationApplier,
) -> None:
    if any(handler.name == name for handler in _CACHE_OPERATION_HANDLERS):
        return
    _CACHE_OPERATION_HANDLERS.append(
        CacheOperationHandler(
            name=name,
            pop_pending_operations=pop_pending_operations,
            apply_operations=apply_operations,
        )
    )


async def apply_registered_cache_operations(session: AsyncSession) -> None:
    for handler in _CACHE_OPERATION_HANDLERS:
        await handler.apply_operations(handler.pop_pending_operations(session))


def clear_registered_cache_operations(session: AsyncSession) -> None:
    for handler in _CACHE_OPERATION_HANDLERS:
        handler.pop_pending_operations(session)


def registered_cache_handler_names() -> tuple[str, ...]:
    return tuple(handler.name for handler in _CACHE_OPERATION_HANDLERS)


register_cache_handler(
    name="session-cache",
    pop_pending_operations=pop_pending_session_cache_operations,
    apply_operations=apply_session_cache_operations,
)
register_cache_handler(
    name="account-dashboard-cache",
    pop_pending_operations=pop_pending_account_dashboard_cache_operations,
    apply_operations=apply_account_dashboard_cache_operations,
)
register_cache_handler(
    name="account-profile-cache",
    pop_pending_operations=pop_pending_account_profile_cache_operations,
    apply_operations=apply_account_profile_cache_operations,
)
register_cache_handler(
    name="push-devices-cache",
    pop_pending_operations=pop_pending_push_devices_cache_operations,
    apply_operations=apply_push_devices_cache_operations,
)
register_cache_handler(
    name="trade-info-cache",
    pop_pending_operations=pop_pending_trade_info_cache_operations,
    apply_operations=apply_trade_info_cache_operations,
)
