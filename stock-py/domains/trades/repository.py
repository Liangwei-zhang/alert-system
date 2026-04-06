"""
Trade repository - data access layer for trades.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.models.trades import Trade, TradeAction, TradeStatus


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradeRepository:
    """Repository for Trade data access."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: Async SQLAlchemy session.
        """
        self.session = session

    async def get_by_id(self, trade_id: str) -> Optional[Trade]:
        """
        Get trade by ID.

        Args:
            trade_id: The trade UUID.

        Returns:
            Trade if found, None otherwise.
        """
        result = await self.session.execute(select(Trade).where(Trade.id == trade_id))
        return result.scalar_one_or_none()

    async def get_by_id_for_user(self, trade_id: str, user_id: int) -> Optional[Trade]:
        """
        Get trade by ID for a specific user.

        Args:
            trade_id: The trade UUID.
            user_id: The user ID.

        Returns:
            Trade if found and belongs to user, None otherwise.
        """
        result = await self.session.execute(
            select(Trade).where(Trade.id == trade_id, Trade.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, token: str) -> Optional[Trade]:
        """
        Get trade by link token.

        Args:
            token: The link token.

        Returns:
            Trade if found, None otherwise.
        """
        result = await self.session.execute(select(Trade).where(Trade.link_token == token))
        return result.scalar_one_or_none()

    async def create(
        self,
        trade_id: str,
        user_id: int,
        symbol: str,
        action: str,
        suggested_shares: float,
        suggested_price: float,
        suggested_amount: float,
        link_token: str,
        link_sig: str,
        expires_at: datetime,
        extra: Optional[dict] = None,
    ) -> Trade:
        """
        Create a new trade.

        Args:
            trade_id: The trade UUID.
            user_id: The user ID.
            symbol: Stock symbol.
            action: Trade action (buy/sell/add).
            suggested_shares: Suggested number of shares.
            suggested_price: Suggested price per share.
            suggested_amount: Suggested total amount.
            link_token: Link token for public access.
            link_sig: HMAC signature.
            expires_at: Link expiration time.
            extra: Optional extra metadata.

        Returns:
            Created trade.
        """
        trade = Trade(
            id=trade_id,
            user_id=user_id,
            symbol=symbol,
            action=TradeAction(action),
            suggested_shares=suggested_shares,
            suggested_price=suggested_price,
            suggested_amount=suggested_amount,
            link_token=link_token,
            link_sig=link_sig,
            expires_at=expires_at,
            extra=None if extra is None else json.dumps(extra),
            status=TradeStatus.PENDING,
        )

        self.session.add(trade)
        await self.session.flush()
        return trade

    async def record_execution(
        self,
        trade_id: str,
        status: TradeStatus,
        actual_shares: float,
        actual_price: float,
        actual_amount: float,
    ) -> bool:
        """
        Confirm a trade with actual execution values.

        Args:
            trade_id: The trade UUID.
            actual_shares: Actual shares executed.
            actual_price: Actual price per share.
            actual_amount: Actual total amount.

        Returns:
            True if updated, False if trade not found or not pending.
        """
        result = await self.session.execute(
            update(Trade)
            .where(Trade.id == trade_id, Trade.status == TradeStatus.PENDING)
            .values(
                status=status,
                actual_shares=actual_shares,
                actual_price=actual_price,
                actual_amount=actual_amount,
                confirmed_at=utcnow(),
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def confirm(
        self,
        trade_id: str,
        actual_shares: float,
        actual_price: float,
        actual_amount: float,
    ) -> bool:
        return await self.record_execution(
            trade_id=trade_id,
            status=TradeStatus.CONFIRMED,
            actual_shares=actual_shares,
            actual_price=actual_price,
            actual_amount=actual_amount,
        )

    async def adjust(
        self, trade_id: str, actual_shares: float, actual_price: float, actual_amount: float
    ) -> bool:
        """
        Adjust a trade with custom execution values.

        Args:
            trade_id: The trade UUID.
            actual_shares: Actual shares executed.
            actual_price: Actual price per share.
            actual_amount: Actual total amount.

        Returns:
            True if updated, False if trade not found or not pending.
        """
        return await self.record_execution(
            trade_id=trade_id,
            status=TradeStatus.ADJUSTED,
            actual_shares=actual_shares,
            actual_price=actual_price,
            actual_amount=actual_amount,
        )

    async def mark_ignored(self, trade_id: str) -> bool:
        """
        Ignore a trade.

        Args:
            trade_id: The trade UUID.

        Returns:
            True if updated, False if trade not found or not pending.
        """
        result = await self.session.execute(
            update(Trade)
            .where(Trade.id == trade_id, Trade.status == TradeStatus.PENDING)
            .values(
                status=TradeStatus.IGNORED,
                confirmed_at=utcnow(),
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def ignore(self, trade_id: str) -> bool:
        return await self.mark_ignored(trade_id)

    def _apply_admin_trade_filters(
        self,
        stmt,
        *,
        status: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        symbol: str | None = None,
        expired_only: bool = False,
        claimed_only: bool = False,
        claimed_by_operator_id: int | None = None,
    ):
        if status is not None:
            stmt = stmt.where(Trade.status == TradeStatus(str(status).strip().lower()))
        if action is not None:
            stmt = stmt.where(Trade.action == TradeAction(str(action).strip().lower()))
        if user_id is not None:
            stmt = stmt.where(Trade.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(Trade.symbol == str(symbol).strip().upper())
        if claimed_only:
            stmt = stmt.where(Trade.claimed_by_operator_id.is_not(None))
        if claimed_by_operator_id is not None:
            stmt = stmt.where(Trade.claimed_by_operator_id == claimed_by_operator_id)
        if expired_only:
            stmt = stmt.where(
                or_(
                    Trade.status == TradeStatus.EXPIRED,
                    (Trade.status == TradeStatus.PENDING) & (Trade.expires_at < utcnow()),
                )
            )
        return stmt

    async def list_admin_trades(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        symbol: str | None = None,
        expired_only: bool = False,
        claimed_only: bool = False,
        claimed_by_operator_id: int | None = None,
    ) -> list[Trade]:
        stmt = self._apply_admin_trade_filters(
            select(Trade),
            status=status,
            action=action,
            user_id=user_id,
            symbol=symbol,
            expired_only=expired_only,
            claimed_only=claimed_only,
            claimed_by_operator_id=claimed_by_operator_id,
        )
        result = await self.session.execute(
            stmt.order_by(Trade.expires_at.asc(), Trade.created_at.desc(), Trade.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_admin_trades(
        self,
        *,
        status: str | None = None,
        action: str | None = None,
        user_id: int | None = None,
        symbol: str | None = None,
        expired_only: bool = False,
        claimed_only: bool = False,
        claimed_by_operator_id: int | None = None,
    ) -> int:
        stmt = self._apply_admin_trade_filters(
            select(func.count(Trade.id)),
            status=status,
            action=action,
            user_id=user_id,
            symbol=symbol,
            expired_only=expired_only,
            claimed_only=claimed_only,
            claimed_by_operator_id=claimed_by_operator_id,
        )
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def list_claimable_trades(
        self,
        *,
        limit: int = 100,
        user_id: int | None = None,
        symbol: str | None = None,
    ) -> list[Trade]:
        stmt = select(Trade).where(
            Trade.status == TradeStatus.PENDING,
            Trade.expires_at >= utcnow(),
            Trade.claimed_by_operator_id.is_(None),
        )
        if user_id is not None:
            stmt = stmt.where(Trade.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(Trade.symbol == str(symbol).strip().upper())
        result = await self.session.execute(
            stmt.order_by(Trade.created_at.asc(), Trade.id.asc()).limit(limit)
        )
        return list(result.scalars().all())

    async def count_claimable_trades(
        self,
        *,
        user_id: int | None = None,
        symbol: str | None = None,
    ) -> int:
        stmt = select(func.count(Trade.id)).where(
            Trade.status == TradeStatus.PENDING,
            Trade.expires_at >= utcnow(),
            Trade.claimed_by_operator_id.is_(None),
        )
        if user_id is not None:
            stmt = stmt.where(Trade.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(Trade.symbol == str(symbol).strip().upper())
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def count_expirable_trades(
        self,
        *,
        user_id: int | None = None,
        symbol: str | None = None,
    ) -> int:
        stmt = select(func.count(Trade.id)).where(
            Trade.status == TradeStatus.PENDING,
            Trade.expires_at < utcnow(),
        )
        if user_id is not None:
            stmt = stmt.where(Trade.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(Trade.symbol == str(symbol).strip().upper())
        result = await self.session.execute(stmt)
        return int(result.scalar_one() or 0)

    async def get_claim_latency_stats(
        self,
        *,
        since: datetime | None = None,
        limit: int = 1000,
    ) -> dict[str, float | int]:
        window_start = since or (utcnow() - timedelta(days=7))
        result = await self.session.execute(
            select(Trade.created_at, Trade.claimed_at)
            .where(
                Trade.claimed_at.is_not(None),
                Trade.created_at.is_not(None),
                Trade.claimed_at >= window_start,
            )
            .order_by(Trade.claimed_at.desc(), Trade.id.desc())
            .limit(limit)
        )
        latencies: list[float] = []
        for created_at, claimed_at in result.all():
            if created_at is None or claimed_at is None:
                continue
            latencies.append(max((claimed_at - created_at).total_seconds(), 0.0))

        if not latencies:
            return {"count": 0, "avg_seconds": 0.0, "max_seconds": 0.0}
        return {
            "count": len(latencies),
            "avg_seconds": sum(latencies) / len(latencies),
            "max_seconds": max(latencies),
        }

    async def claim(self, trade_id: str, operator_user_id: int) -> Trade | None:
        trade = await self.get_by_id(trade_id)
        if trade is None:
            return None
        if trade.status != TradeStatus.PENDING:
            return None
        if trade.expires_at < utcnow():
            return None
        if trade.claimed_by_operator_id is not None:
            return None
        trade.claimed_by_operator_id = operator_user_id
        trade.claimed_at = utcnow()
        trade.updated_at = utcnow()
        await self.session.flush()
        return trade

    async def list_expirable_trades(
        self,
        *,
        limit: int = 100,
        user_id: int | None = None,
        symbol: str | None = None,
    ) -> list[Trade]:
        stmt = select(Trade).where(
            Trade.status == TradeStatus.PENDING,
            Trade.expires_at < utcnow(),
        )
        if user_id is not None:
            stmt = stmt.where(Trade.user_id == user_id)
        if symbol is not None:
            stmt = stmt.where(Trade.symbol == str(symbol).strip().upper())
        result = await self.session.execute(
            stmt.order_by(Trade.expires_at.asc(), Trade.created_at.desc(), Trade.id.desc()).limit(
                limit
            )
        )
        return list(result.scalars().all())

    async def mark_expired(self, trade_id: str) -> Trade | None:
        trade = await self.get_by_id(trade_id)
        if trade is None:
            return None
        if trade.status != TradeStatus.PENDING:
            return None
        if trade.expires_at >= utcnow():
            return None
        trade.status = TradeStatus.EXPIRED
        trade.updated_at = utcnow()
        await self.session.flush()
        return trade

    async def is_expired(self, trade: Trade) -> bool:
        """
        Check if a trade link has expired.

        Args:
            trade: The trade to check.

        Returns:
            True if expired, False otherwise.
        """
        return utcnow() > trade.expires_at

    async def get_user_pending_trades(self, user_id: int) -> list[Trade]:
        """
        Get all pending trades for a user.

        Args:
            user_id: The user ID.

        Returns:
            List of pending trades.
        """
        result = await self.session.execute(
            select(Trade)
            .where(Trade.user_id == user_id, Trade.status == TradeStatus.PENDING)
            .order_by(Trade.created_at.desc())
        )
        return list(result.scalars().all())
