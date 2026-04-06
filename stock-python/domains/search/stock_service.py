"""
Stock service - business logic for stock data.
"""
import asyncio
from typing import Optional, List
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from domains.search.stock import Stock, Watchlist, WatchlistItem
from domains.search.stock import StockQuote, StockSearchResult, HistoricalData
from domains.market_data.data_source import DataSourceFactory
from infra.config import settings


class StockService:
    """Service for stock-related operations."""

    def __init__(self):
        self._cache: Optional[redis.Redis] = None

    async def _get_cache(self) -> redis.Redis:
        if self._cache is None:
            self._cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._cache

    # =====================
    # Quote Operations
    # =====================

    async def get_quote(
        self, symbol: str, source: str = "yahoo"
    ) -> Optional[StockQuote]:
        """Get real-time quote for a symbol."""
        # Try cache first
        cache = await self._get_cache()
        cache_key = f"stock:quote:{symbol.upper()}"

        cached = await cache.get(cache_key)
        if cached:
            import json
            data = json.loads(cached)
            return StockQuote(
                symbol=data["symbol"],
                name=data["name"],
                price=data["price"],
                change=data["change"],
                change_percent=data["change_percent"],
                volume=data["volume"],
                market_cap=data.get("market_cap"),
                previous_close=data["previous_close"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )

        # Fetch from data source
        return await DataSourceFactory.get_quote(symbol, source)

    async def get_quotes_batch(
        self, symbols: List[str], source: str = "yahoo"
    ) -> List[Optional[StockQuote]]:
        """Get quotes for multiple symbols in parallel."""
        tasks = [self.get_quote(s, source) for s in symbols]
        return await asyncio.gather(*tasks)

    # =====================
    # Search Operations
    # =====================

    async def search_stocks(
        self, query: str, source: str = "yahoo"
    ) -> List[StockSearchResult]:
        """Search for stocks by query."""
        return await DataSourceFactory.search(query, source)

    # =====================
    # Historical Data
    # =====================

    async def get_historical(
        self, symbol: str, period: str = "1mo", source: str = "yahoo"
    ) -> List[HistoricalData]:
        """Get historical data for a symbol."""
        return await DataSourceFactory.get_historical(symbol, period, source)

    # =====================
    # Database Operations
    # =====================

    async def get_stock_by_symbol(
        self, db: AsyncSession, symbol: str
    ) -> Optional[Stock]:
        """Get stock from database by symbol."""
        result = await db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalar_one_or_none()

    async def get_all_stocks(
        self, db: AsyncSession, limit: int = 100, offset: int = 0
    ) -> List[Stock]:
        """Get all stocks from database."""
        result = await db.execute(
            select(Stock).order_by(Stock.symbol).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def create_stock(
        self,
        db: AsyncSession,
        symbol: str,
        name: str,
        exchange: str = "NASDAQ",
        sector: Optional[str] = None,
    ) -> Stock:
        """Create a new stock in the database."""
        stock = Stock(
            symbol=symbol.upper(),
            name=name,
            exchange=exchange,
            sector=sector,
        )
        db.add(stock)
        await db.commit()
        await db.refresh(stock)
        return stock

    async def update_stock_price(
        self,
        db: AsyncSession,
        symbol: str,
        price: float,
        previous_close: Optional[float] = None,
        volume: Optional[int] = None,
        market_cap: Optional[float] = None,
    ) -> Optional[Stock]:
        """Update stock price in database."""
        stock = await self.get_stock_by_symbol(db, symbol)
        if stock:
            stock.current_price = price
            if previous_close is not None:
                stock.previous_close = previous_close
            if volume is not None:
                stock.volume = volume
            if market_cap is not None:
                stock.market_cap = market_cap
            stock.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(stock)
        return stock

    # =====================
    # Watchlist Operations
    # =====================

    async def get_user_watchlists(
        self, db: AsyncSession, user_id: int
    ) -> List[Watchlist]:
        """Get all watchlists for a user."""
        result = await db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.name)
        )
        return list(result.scalars().all())

    async def get_watchlist(
        self, db: AsyncSession, watchlist_id: int, user_id: int
    ) -> Optional[Watchlist]:
        """Get a specific watchlist."""
        result = await db.execute(
            select(Watchlist).where(
                Watchlist.id == watchlist_id,
                Watchlist.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_watchlist(
        self, db: AsyncSession, user_id: int, name: str
    ) -> Watchlist:
        """Create a new watchlist."""
        watchlist = Watchlist(user_id=user_id, name=name)
        db.add(watchlist)
        await db.commit()
        await db.refresh(watchlist)
        return watchlist

    async def update_watchlist(
        self, db: AsyncSession, watchlist_id: int, user_id: int, name: str
    ) -> Optional[Watchlist]:
        """Update watchlist name."""
        watchlist = await self.get_watchlist(db, watchlist_id, user_id)
        if watchlist:
            watchlist.name = name
            watchlist.updated_at = datetime.utcnow()
            await db.commit()
            await db.refresh(watchlist)
        return watchlist

    async def delete_watchlist(
        self, db: AsyncSession, watchlist_id: int, user_id: int
    ) -> bool:
        """Delete a watchlist."""
        watchlist = await self.get_watchlist(db, watchlist_id, user_id)
        if watchlist:
            await db.delete(watchlist)
            await db.commit()
            return True
        return False

    async def add_to_watchlist(
        self,
        db: AsyncSession,
        watchlist_id: int,
        stock_symbol: str,
        notes: Optional[str] = None,
    ) -> Optional[WatchlistItem]:
        """Add a stock to a watchlist."""
        # Get or create stock
        stock = await self.get_stock_by_symbol(db, stock_symbol)
        if not stock:
            # Try to fetch from API
            quote = await self.get_quote(stock_symbol)
            if quote:
                stock = await self.create_stock(
                    db, quote.symbol, quote.name, "NASDAQ"
                )
            else:
                return None

        # Check if already in watchlist
        result = await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist_id,
                WatchlistItem.stock_id == stock.id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        # Add to watchlist
        item = WatchlistItem(
            watchlist_id=watchlist_id,
            stock_id=stock.id,
            notes=notes,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    async def remove_from_watchlist(
        self, db: AsyncSession, watchlist_id: int, stock_id: int
    ) -> bool:
        """Remove a stock from a watchlist."""
        result = await db.execute(
            select(WatchlistItem).where(
                WatchlistItem.watchlist_id == watchlist_id,
                WatchlistItem.stock_id == stock_id,
            )
        )
        item = result.scalar_one_or_none()
        if item:
            await db.delete(item)
            await db.commit()
            return True
        return False

    async def get_watchlist_with_prices(
        self, db: AsyncSession, watchlist_id: int, user_id: int
    ) -> Optional[dict]:
        """Get watchlist with real-time prices."""
        watchlist = await self.get_watchlist(db, watchlist_id, user_id)
        if not watchlist:
            return None

        # Get all items
        result = await db.execute(
            select(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist_id)
        )
        items = list(result.scalars().all())

        # Get prices for all stocks
        symbols = [item.stock.symbol for item in items if item.stock]
        quotes = await self.get_quotes_batch(symbols)

        # Build response
        response = {
            "id": watchlist.id,
            "name": watchlist.name,
            "user_id": watchlist.user_id,
            "created_at": watchlist.created_at,
            "updated_at": watchlist.updated_at,
            "items": [],
        }

        for item, quote in zip(items, quotes):
            item_data = {
                "id": item.id,
                "stock_id": item.stock_id,
                "symbol": item.stock.symbol,
                "name": item.stock.name,
                "notes": item.notes,
                "added_at": item.added_at,
            }
            if quote:
                item_data["price"] = quote.price
                item_data["change"] = quote.change
                item_data["change_percent"] = quote.change_percent
            else:
                item_data["price"] = item.stock.current_price
                item_data["change"] = 0
                item_data["change_percent"] = 0

            response["items"].append(item_data)

        return response


# Singleton instance
stock_service = StockService()