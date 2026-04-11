from __future__ import annotations

from domains.portfolio.extra_payload import deserialize_portfolio_extra
from domains.portfolio.policies import PortfolioPolicy
from domains.portfolio.repository import PortfolioRepository
from domains.portfolio.schemas import (
    CreatePortfolioRequest,
    PortfolioItemResponse,
    UpdatePortfolioRequest,
)
from infra.cache.account_dashboard_cache import schedule_invalidate_account_dashboard
from infra.core.errors import AppError
from infra.events.outbox import OutboxPublisher


class PortfolioService:
    def __init__(self, repository: PortfolioRepository) -> None:
        self.repository = repository
        self.policy = PortfolioPolicy()
        self.outbox = OutboxPublisher(repository.session)

    @staticmethod
    def _to_response(item) -> PortfolioItemResponse:
        return PortfolioItemResponse(
            id=item.id,
            symbol=item.symbol,
            shares=item.shares,
            avg_cost=float(item.avg_cost),
            total_capital=float(item.total_capital),
            target_profit=float(item.target_profit),
            stop_loss=float(item.stop_loss),
            notify=item.notify,
            notes=item.notes,
            extra=deserialize_portfolio_extra(getattr(item, "extra", None)),
            updated_at=item.updated_at,
        )

    async def list_positions(self, user_id: int) -> list[PortfolioItemResponse]:
        items = await self.repository.list_by_user(user_id)
        return [self._to_response(item) for item in items]

    async def add_position(
        self, user_id: int, plan: str, request: CreatePortfolioRequest
    ) -> PortfolioItemResponse:
        symbol = self.policy.normalize_symbol(request.symbol)
        self.policy.validate_numbers(request.shares, request.avg_cost)
        existing = await self.repository.get_by_user_and_symbol(user_id, symbol)
        if existing is None:
            current_count = len(await self.repository.list_by_user(user_id))
            self.policy.enforce_plan_limit(plan, current_count)

        item = await self.repository.create(
            user_id=user_id,
            symbol=symbol,
            shares=request.shares,
            avg_cost=request.avg_cost,
            target_profit=request.target_profit,
            stop_loss=request.stop_loss,
            notify=request.notify,
            notes=request.notes,
        )
        await self.outbox.publish_after_commit(
            topic="portfolio.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": symbol, "action": "upsert"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
        return self._to_response(item)

    async def update_position(
        self, user_id: int, item_id: int, request: UpdatePortfolioRequest
    ) -> PortfolioItemResponse:
        item = await self.repository.get_by_id(item_id)
        if item is None or item.user_id != user_id:
            raise AppError("portfolio_not_found", "Position not found", status_code=404)

        updates = request.model_dump(exclude_unset=True)
        next_shares = updates.get("shares", item.shares)
        next_avg_cost = updates.get("avg_cost", float(item.avg_cost))
        self.policy.validate_numbers(int(next_shares), float(next_avg_cost))
        item = await self.repository.update(item, updates)
        await self.outbox.publish_after_commit(
            topic="portfolio.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": item.symbol, "action": "update"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
        return self._to_response(item)

    async def delete_position(self, user_id: int, item_id: int) -> None:
        item = await self.repository.get_by_id(item_id)
        if item is None or item.user_id != user_id:
            raise AppError("portfolio_not_found", "Position not found", status_code=404)
        symbol = item.symbol
        await self.repository.delete(item)
        await self.outbox.publish_after_commit(
            topic="portfolio.changed",
            key=str(user_id),
            payload={"user_id": user_id, "symbol": symbol, "action": "delete"},
        )
        schedule_invalidate_account_dashboard(getattr(self.repository, "session", None), user_id)
