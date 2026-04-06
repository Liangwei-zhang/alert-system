"""
Scanner service - watchlist monitoring and price change detection.
"""
from typing import List, Dict, Optional
from datetime import datetime
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from domains.search.stock import Watchlist, WatchlistItem, Stock
from domains.search.stock_service import StockService
from infra.config import settings


class PriceChange:
    """Represents a price change alert."""
    def __init__(
        self,
        symbol: str,
        name: str,
        old_price: float,
        new_price: float,
        change_percent: float,
        direction: str  # "up" or "down"
    ):
        self.symbol = symbol
        self.name = name
        self.old_price = old_price
        self.new_price = new_price
        self.change_percent = change_percent
        self.direction = direction
        self.timestamp = datetime.utcnow()


class ScannerService:
    """Service for scanning watchlists and detecting price changes."""

    def __init__(self):
        self._cache: Optional[redis.Redis] = None
        self._stock_service = StockService()

    async def _get_cache(self) -> redis.Redis:
        if self._cache is None:
            self._cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._cache

    async def get_watchlist_stocks(
        self, db: AsyncSession, watchlist_id: int
    ) -> List[Dict]:
        """Get all stocks in a watchlist with current prices."""
        result = await db.execute(
            select(WatchlistItem)
            .where(WatchlistItem.watchlist_id == watchlist_id)
            .options(
                WatchlistItem.stock  # Eager load stock relationship
            )
        )
        items = result.scalars().all()

        stocks = []
        for item in items:
            stock = item.stock
            quote = await self._stock_service.get_quote(stock.symbol)
            stocks.append({
                "id": stock.id,
                "symbol": stock.symbol,
                "name": stock.name,
                "previous_close": float(stock.current_price or 0) if stock.current_price else None,
                "current_price": quote.price if quote else None,
                "change": quote.change if quote else None,
                "change_percent": quote.change_percent if quote else None,
            })
        return stocks

    async def scan_watchlist(
        self, db: AsyncSession, watchlist_id: int, threshold_percent: float = 5.0
    ) -> List[PriceChange]:
        """Scan watchlist for significant price changes."""
        cache = await self._get_cache()
        key_prefix = f"scanner:last_price:{watchlist_id}"

        stocks = await self.get_watchlist_stocks(db, watchlist_id)
        changes = []

        for stock in stocks:
            if not stock.get("current_price"):
                continue

            symbol = stock["symbol"]
            current_price = stock["current_price"]

            # Get last recorded price
            last_price_key = f"{key_prefix}:{symbol}"
            last_price_str = await cache.get(last_price_key)

            if last_price_str:
                last_price = float(last_price_str)
                if last_price > 0:
                    change_pct = ((current_price - last_price) / last_price) * 100

                    if abs(change_pct) >= threshold_percent:
                        direction = "up" if change_pct > 0 else "down"
                        changes.append(PriceChange(
                            symbol=symbol,
                            name=stock["name"],
                            old_price=last_price,
                            new_price=current_price,
                            change_percent=change_pct,
                            direction=direction
                        ))

            # Update last price
            await cache.set(last_price_key, str(current_price), ex=86400 * 7)  # 7 days

        return changes

    async def scan_all_watchlists(
        self, db: AsyncSession, threshold_percent: float = 5.0
    ) -> Dict[int, List[PriceChange]]:
        """Scan all user watchlists."""
        result = await db.execute(select(Watchlist))
        watchlists = result.scalars().all()

        all_changes = {}
        for wl in watchlists:
            changes = await self.scan_watchlist(db, wl.id, threshold_percent)
            if changes:
                all_changes[wl.id] = changes

        return all_changes


# Singleton instance
scanner_service = ScannerService()