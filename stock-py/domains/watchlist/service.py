from __future__ import annotations

from domains.watchlist.policies import WatchlistPolicy
from domains.watchlist.repository import WatchlistRepository
from domains.watchlist.schemas import (
    CreateWatchlistRequest,
    UpdateWatchlistRequest,
    WatchlistItemResponse,
)
from infra.cache.account_dashboard_cache import schedule_invalidate_account_dashboard
from infra.core.errors import AppError
from infra.events.outbox import OutboxPublisher


class WatchlistService:
    def __init__(self, repository: WatchlistRepository) -> None:
        self.repository = repository
        self.policy = WatchlistPolicy()
        self.outbox = OutboxPublisher(repository.session)

    async def list_items(self, user_id: int) -> list[WatchlistItemResponse]:
        items = await self.repository.list_by_user(user_id)
        return [
            WatchlistItemResponse(
                id=item.id,
                symbol=item.symbol,
                notify=item.notify,
                min_score=item.min_score,
                created_at=item.created_at,
            )
            for item in items
        ]

    async def add_item(
        self, user_id: int, plan: str, request: CreateWatchlistRequest
    ) -> WatchlistItemResponse:
        symbol = self.policy.normalize_symbol(request.symbol)
        self.policy.validate_min_score(request.min_score)
        existing = await self.repository.get_by_user_and_symbol(user_id, symbol)
        if existing is None:
            current_count = len(await self.repository.list_by_user(user_id))
            self.policy.enforce_plan_limit(plan, current_count)

        item = await self.repository.create(user_id, symbol, request.notify, request.min_score)
        await self.outbox.publish_after_commit(
            topic="watchlist.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": symbol, "action": "upsert"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
        return WatchlistItemResponse(
            id=item.id,
            symbol=item.symbol,
            notify=item.notify,
            min_score=item.min_score,
            created_at=item.created_at,
        )

    async def update_item(
        self, user_id: int, item_id: int, request: UpdateWatchlistRequest
    ) -> WatchlistItemResponse:
        item = await self.repository.get_by_id(item_id)
        if item is None or item.user_id != user_id:
            raise AppError("watchlist_not_found", "Watchlist item not found", status_code=404)
        if request.min_score is not None:
            self.policy.validate_min_score(request.min_score)
        item = await self.repository.update(item, request.notify, request.min_score)
        await self.outbox.publish_after_commit(
            topic="watchlist.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": item.symbol, "action": "update"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
        return WatchlistItemResponse(
            id=item.id,
            symbol=item.symbol,
            notify=item.notify,
            min_score=item.min_score,
            created_at=item.created_at,
        )

    async def delete_item(self, user_id: int, item_id: int) -> None:
        item = await self.repository.get_by_id(item_id)
        if item is None or item.user_id != user_id:
            raise AppError("watchlist_not_found", "Watchlist item not found", status_code=404)
        symbol = item.symbol
        await self.repository.delete(item)
        await self.outbox.publish_after_commit(
            topic="watchlist.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": symbol, "action": "delete"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
