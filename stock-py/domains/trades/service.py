"""
Trade service - business logic for trade confirmations.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from domains.notifications.repository import NotificationRepository, ReceiptRepository
from domains.portfolio.repository import PortfolioRepository
from domains.trades.link_security import get_link_signer
from domains.trades.repository import TradeRepository
from infra.cache.trade_info_cache import get_or_load_trade_snapshot, schedule_invalidate_trade_info
from infra.core.errors import AppError
from infra.db.models.trades import Trade, TradeAction, TradeStatus
from infra.events.outbox import OutboxEvent, OutboxPublisher


@dataclass(slots=True)
class TradeSnapshot:
    id: str
    user_id: int
    symbol: str
    action: TradeAction
    suggested_shares: float
    suggested_price: float
    suggested_amount: float
    status: TradeStatus
    expires_at: datetime
    link_token: str
    link_sig: str


class TradeService:
    """Service for trade confirmation operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize service with database session.

        Args:
            session: Async SQLAlchemy session.
        """
        self.session = session
        self.repo = TradeRepository(session)
        self.portfolio_repository = PortfolioRepository(session)
        self.notification_repository = NotificationRepository(session)
        self.receipt_repository = ReceiptRepository(session)
        self.outbox = OutboxPublisher(session)
        self.signer = get_link_signer()

    def _schedule_trade_info_invalidation(self, trade_id: str) -> None:
        schedule_invalidate_trade_info(self.session, trade_id)

    @staticmethod
    def _serialize_trade_snapshot_payload(trade: Trade) -> dict:
        return {
            "id": trade.id,
            "user_id": int(trade.user_id),
            "symbol": trade.symbol,
            "action": trade.action.value,
            "suggested_shares": float(trade.suggested_shares),
            "suggested_price": float(trade.suggested_price),
            "suggested_amount": float(trade.suggested_amount),
            "status": trade.status.value,
            "expires_at": trade.expires_at.isoformat(),
            "link_token": trade.link_token,
            "link_sig": trade.link_sig,
        }

    @staticmethod
    def _deserialize_trade_snapshot(payload: dict) -> TradeSnapshot:
        return TradeSnapshot(
            id=str(payload["id"]),
            user_id=int(payload["user_id"]),
            symbol=str(payload["symbol"]),
            action=TradeAction(str(payload["action"])),
            suggested_shares=float(payload["suggested_shares"]),
            suggested_price=float(payload["suggested_price"]),
            suggested_amount=float(payload["suggested_amount"]),
            status=TradeStatus(str(payload["status"])),
            expires_at=datetime.fromisoformat(str(payload["expires_at"])),
            link_token=str(payload["link_token"]),
            link_sig=str(payload["link_sig"]),
        )

    async def _load_trade_snapshot_payload(self, trade_id: str) -> dict | None:
        trade = await self.repo.get_by_id(trade_id)
        if trade is None:
            return None
        return self._serialize_trade_snapshot_payload(trade)

    async def get_trade_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID."""
        return await self.repo.get_by_id(trade_id)

    async def get_trade_for_user(self, trade_id: str, user_id: int) -> Optional[Trade]:
        """Get trade by ID for a specific user."""
        return await self.repo.get_by_id_for_user(trade_id, user_id)

    async def get_trade_info_by_id(self, trade_id: str) -> TradeSnapshot | None:
        payload = await get_or_load_trade_snapshot(
            trade_id,
            lambda: self._load_trade_snapshot_payload(trade_id),
        )
        if payload is None:
            return None
        return self._deserialize_trade_snapshot(payload)

    async def get_trade_info_for_user(self, trade_id: str, user_id: int) -> TradeSnapshot | None:
        trade = await self.get_trade_info_by_id(trade_id)
        if trade is None or trade.user_id != user_id:
            return None
        return trade

    def verify_link_token(self, trade: Trade, token: str) -> bool:
        """
        Verify a link token against a trade.

        Args:
            trade: The trade to verify.
            token: The token to verify.

        Returns:
            True if token is valid.
        """
        if trade.link_token != token:
            return False

        return self.signer.verify(
            token=token, user_id=trade.user_id, symbol=trade.symbol, signature=trade.link_sig
        )

    def is_expired(self, trade: Trade) -> bool:
        """Check if a trade has expired."""
        expires_at = trade.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > expires_at

    def get_unavailable_error(self, trade: Trade) -> Optional[str]:
        """
        Get error message if trade is unavailable for processing.

        Args:
            trade: The trade to check.

        Returns:
            Error message if unavailable, None if available.
        """
        if trade.status != TradeStatus.PENDING:
            return "This trade has already been processed"

        if self.is_expired(trade):
            return "This trade has expired"

        return None

    async def confirm_trade(
        self,
        trade: Trade,
        actual_shares: Optional[float] = None,
        actual_price: Optional[float] = None,
    ) -> float:
        """
        Confirm a trade and apply to portfolio.

        Args:
            trade: The trade to confirm.
            actual_shares: Optional override for shares.
            actual_price: Optional override for price.

        Returns:
            Actual amount executed.
        """
        shares = float(actual_shares or trade.suggested_shares)
        price = float(actual_price or trade.suggested_price)
        actual_amount = round(shares * price, 2)

        updated = await self.repo.record_execution(
            trade_id=trade.id,
            status=TradeStatus.CONFIRMED,
            actual_shares=shares,
            actual_price=price,
            actual_amount=actual_amount,
        )
        if not updated:
            raise AppError("trade_not_available", "Trade is no longer pending", status_code=409)
        self._schedule_trade_info_invalidation(trade.id)

        if trade.action in (TradeAction.BUY, TradeAction.ADD):
            await self._apply_buy_to_portfolio(trade, shares, price, actual_amount)
        elif trade.action == TradeAction.SELL:
            await self._apply_sell_to_portfolio(trade, shares, price)

        await self._publish_trade_action(
            trade=trade,
            status=TradeStatus.CONFIRMED,
            actual_shares=shares,
            actual_price=price,
            actual_amount=actual_amount,
        )

        return actual_amount

    async def ignore_trade(self, trade: Trade) -> bool:
        """
        Ignore a trade.

        Args:
            trade: The trade to ignore.

        Returns:
            True if successful.
        """
        ignored = await self.repo.mark_ignored(trade.id)
        if not ignored:
            raise AppError("trade_not_available", "Trade is no longer pending", status_code=409)
        self._schedule_trade_info_invalidation(trade.id)
        await self._publish_trade_action(
            trade=trade,
            status=TradeStatus.IGNORED,
            actual_shares=None,
            actual_price=None,
            actual_amount=None,
        )
        return True

    async def adjust_trade(self, trade: Trade, actual_shares: float, actual_price: float) -> float:
        """
        Adjust and confirm a trade with custom values.

        Args:
            trade: The trade to adjust.
            actual_shares: Actual shares executed.
            actual_price: Actual price per share.

        Returns:
            Actual amount executed.
        """
        actual_amount = round(actual_shares * actual_price, 2)

        updated = await self.repo.record_execution(
            trade_id=trade.id,
            status=TradeStatus.ADJUSTED,
            actual_shares=actual_shares,
            actual_price=actual_price,
            actual_amount=actual_amount,
        )
        if not updated:
            raise AppError("trade_not_available", "Trade is no longer pending", status_code=409)
        self._schedule_trade_info_invalidation(trade.id)

        if trade.action in (TradeAction.BUY, TradeAction.ADD):
            await self._apply_buy_to_portfolio(trade, actual_shares, actual_price, actual_amount)
        elif trade.action == TradeAction.SELL:
            await self._apply_sell_to_portfolio(trade, actual_shares, actual_price)

        await self._publish_trade_action(
            trade=trade,
            status=TradeStatus.ADJUSTED,
            actual_shares=actual_shares,
            actual_price=actual_price,
            actual_amount=actual_amount,
        )

        return actual_amount

    async def _apply_buy_to_portfolio(
        self, trade: Trade, shares: float, price: float, amount: float
    ) -> None:
        """
        Apply a buy trade to user portfolio.

        Args:
            trade: The trade.
            shares: Number of shares.
            price: Price per share.
            amount: Total amount.
        """
        existing = await self.portfolio_repository.get_by_user_and_symbol(
            trade.user_id, trade.symbol
        )
        normalized_shares = self._to_portfolio_shares(shares)

        if existing:
            new_shares, new_avg_cost = self.calculate_buy_position(
                current_shares=int(existing.shares),
                current_avg_cost=float(existing.avg_cost),
                actual_shares=normalized_shares,
                actual_price=price,
            )
            await self.portfolio_repository.update(
                existing,
                {
                    "shares": new_shares,
                    "avg_cost": new_avg_cost,
                },
            )
        else:
            await self.portfolio_repository.create(
                user_id=trade.user_id,
                symbol=trade.symbol,
                shares=normalized_shares,
                avg_cost=price,
                target_profit=0.15,
                stop_loss=0.08,
                notify=True,
                notes=None,
            )

    async def _apply_sell_to_portfolio(self, trade: Trade, shares: float, price: float) -> None:
        """
        Apply a sell trade to user portfolio.

        Args:
            trade: The trade.
            shares: Number of shares to sell.
            price: Price per share.
        """
        position = await self.portfolio_repository.get_by_user_and_symbol(
            trade.user_id, trade.symbol
        )

        if position:
            remaining = self.calculate_remaining_shares(int(position.shares), shares)
            if remaining <= 0:
                await self.portfolio_repository.delete(position)
            else:
                await self.portfolio_repository.update(position, {"shares": remaining})

    async def _publish_trade_action(
        self,
        trade: Trade,
        status: TradeStatus,
        actual_shares: float | None,
        actual_price: float | None,
        actual_amount: float | None,
    ) -> None:
        await self.outbox.publish_after_commit(
            topic="trade.action.recorded",
            key=trade.id,
            payload={
                "trade_id": trade.id,
                "user_id": trade.user_id,
                "symbol": trade.symbol,
                "action": trade.action.value,
                "status": status.value,
                "actual_shares": actual_shares,
                "actual_price": actual_price,
                "actual_amount": actual_amount,
            },
        )

    @staticmethod
    def calculate_buy_position(
        current_shares: int,
        current_avg_cost: float,
        actual_shares: int,
        actual_price: float,
    ) -> tuple[int, float]:
        new_shares = current_shares + actual_shares
        if new_shares <= 0:
            return 0, 0.0
        new_avg_cost = round(
            ((current_shares * current_avg_cost) + (actual_shares * actual_price)) / new_shares,
            4,
        )
        return new_shares, new_avg_cost

    @staticmethod
    def calculate_remaining_shares(current_shares: int, actual_shares: float) -> int:
        return current_shares - TradeService._to_portfolio_shares(actual_shares)

    @staticmethod
    def _to_portfolio_shares(shares: float) -> int:
        normalized = int(shares)
        return normalized if normalized > 0 else 1

    def serialize_trade(self, trade: Trade | TradeSnapshot) -> dict:
        """Serialize trade for API response."""
        return {
            "id": trade.id,
            "symbol": trade.symbol,
            "action": trade.action.value,
            "suggested_shares": float(trade.suggested_shares),
            "suggested_price": float(trade.suggested_price),
            "suggested_amount": float(trade.suggested_amount),
            "status": trade.status.value,
        }

    async def acknowledge_receipts(self, trade: Trade) -> None:
        """
        Acknowledge message receipts for a trade.

        Args:
            trade: The trade.
        """
        notification_ids = await self.notification_repository.list_ids_by_trade(
            trade.user_id, trade.id
        )
        if not notification_ids:
            return

        await self.receipt_repository.acknowledge_many(notification_ids, trade.user_id)
        await self.outbox.publish_batch_after_commit(
            OutboxEvent(
                topic="notification.acknowledged",
                key=notification_id,
                payload={
                    "user_id": trade.user_id,
                    "notification_id": notification_id,
                    "trade_id": trade.id,
                },
            )
            for notification_id in notification_ids
        )
