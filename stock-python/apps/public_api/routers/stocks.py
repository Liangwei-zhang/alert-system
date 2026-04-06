"""
Stock API endpoints - search, quote, history, watchlist.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from domains.search.stock_service import stock_service
from infra.database import get_db

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


# =====================
# Request/Response Models
# =====================


class QuoteResponse(BaseModel):
    """Stock quote response."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float] = None
    previous_close: float
    open: float
    high: float
    low: float


class SearchResult(BaseModel):
    """Stock search result."""
    symbol: str
    name: str
    exchange: str
    type: str


class HistoricalDataPoint(BaseModel):
    """Historical data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class HistoricalResponse(BaseModel):
    """Historical data response."""
    symbol: str
    period: str
    data: List[HistoricalDataPoint]


class WatchlistCreate(BaseModel):
    """Watchlist creation request."""
    name: str


class WatchlistUpdate(BaseModel):
    """Watchlist update request."""
    name: str


class WatchlistItemAdd(BaseModel):
    """Add stock to watchlist request."""
    symbol: str
    notes: Optional[str] = None


class WatchlistItemResponse(BaseModel):
    """Watchlist item response."""
    id: int
    symbol: str
    name: str
    price: Optional[float] = None
    change: float = 0
    change_percent: float = 0
    notes: Optional[str] = None
    added_at: str


class WatchlistResponse(BaseModel):
    """Watchlist response."""
    id: int
    name: str
    user_id: int
    items: List[WatchlistItemResponse] = []


# =====================
# Quote Endpoints
# =====================


@router.get("/quote/{symbol}", response_model=QuoteResponse)
async def get_quote(
    symbol: str,
    source: str = Query("yahoo", description="Data source: yahoo, binance"),
):
    """Get real-time quote for a stock symbol."""
    quote = await stock_service.get_quote(symbol, source)

    if not quote:
        raise HTTPException(status_code=404, detail=f"Quote not found for {symbol}")

    return QuoteResponse(
        symbol=quote.symbol,
        name=quote.name,
        price=quote.price,
        change=quote.change,
        change_percent=quote.change_percent,
        volume=quote.volume,
        market_cap=quote.market_cap,
        previous_close=quote.previous_close,
        open=quote.open,
        high=quote.high,
        low=quote.low,
    )


@router.post("/quotes/batch", response_model=List[QuoteResponse])
async def get_quotes_batch(
    symbols: List[str],
    source: str = Query("yahoo"),
):
    """Get quotes for multiple symbols."""
    quotes = await stock_service.get_quotes_batch(symbols, source)

    results = []
    for quote in quotes:
        if quote:
            results.append(
                QuoteResponse(
                    symbol=quote.symbol,
                    name=quote.name,
                    price=quote.price,
                    change=quote.change,
                    change_percent=quote.change_percent,
                    volume=quote.volume,
                    market_cap=quote.market_cap,
                    previous_close=quote.previous_close,
                    open=quote.open,
                    high=quote.high,
                    low=quote.low,
                )
            )

    return results


# =====================
# Search Endpoints
# =====================


@router.get("/search", response_model=List[SearchResult])
async def search_stocks(
    q: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("yahoo"),
):
    """Search for stocks by query."""
    results = await stock_service.search_stocks(q, source)
    return [
        SearchResult(
            symbol=r.symbol,
            name=r.name,
            exchange=r.exchange,
            type=r.type,
        )
        for r in results
    ]


# =====================
# Historical Data Endpoints
# =====================


@router.get("/history/{symbol}", response_model=HistoricalResponse)
async def get_historical(
    symbol: str,
    period: str = Query(
        "1mo",
        description="Period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max",
    ),
    source: str = Query("yahoo"),
):
    """Get historical price data for a symbol."""
    history = await stock_service.get_historical(symbol, period, source)

    if not history:
        raise HTTPException(
            status_code=404, detail=f"Historical data not found for {symbol}"
        )

    return HistoricalResponse(
        symbol=symbol.upper(),
        period=period,
        data=[
            HistoricalDataPoint(
                date=h.date.isoformat(),
                open=h.open,
                high=h.high,
                low=h.low,
                close=h.close,
                volume=h.volume,
            )
            for h in history
        ],
    )


# =====================
# Watchlist Endpoints
# =====================


@router.get("/watchlists", response_model=List[WatchlistResponse])
async def get_watchlists(
    user_id: int = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db),
):
    """Get all watchlists for a user."""
    watchlists = await stock_service.get_user_watchlists(db, user_id)

    return [
        WatchlistResponse(
            id=w.id,
            name=w.name,
            user_id=w.user_id,
            items=[
                WatchlistItemResponse(
                    id=item.id,
                    symbol=item.stock.symbol,
                    name=item.stock.name,
                    price=item.stock.current_price,
                    notes=item.notes,
                    added_at=item.added_at.isoformat(),
                )
                for item in w.items
            ],
        )
        for w in watchlists
    ]


@router.get("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def get_watchlist(
    watchlist_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific watchlist with prices."""
    watchlist = await stock_service.get_watchlist_with_prices(
        db, watchlist_id, user_id
    )

    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return WatchlistResponse(
        id=watchlist["id"],
        name=watchlist["name"],
        user_id=watchlist["user_id"],
        items=[
            WatchlistItemResponse(
                id=item["id"],
                symbol=item["symbol"],
                name=item["name"],
                price=item.get("price"),
                change=item.get("change", 0),
                change_percent=item.get("change_percent", 0),
                notes=item["notes"],
                added_at=item["added_at"],
            )
            for item in watchlist["items"]
        ],
    )


@router.post("/watchlists", response_model=WatchlistResponse)
async def create_watchlist(
    watchlist: WatchlistCreate,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a new watchlist."""
    created = await stock_service.create_watchlist(db, user_id, watchlist.name)

    return WatchlistResponse(
        id=created.id,
        name=created.name,
        user_id=created.user_id,
    )


@router.put("/watchlists/{watchlist_id}", response_model=WatchlistResponse)
async def update_watchlist(
    watchlist_id: int,
    watchlist: WatchlistUpdate,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Update a watchlist."""
    updated = await stock_service.update_watchlist(
        db, watchlist_id, user_id, watchlist.name
    )

    if not updated:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return WatchlistResponse(
        id=updated.id,
        name=updated.name,
        user_id=updated.user_id,
    )


@router.delete("/watchlists/{watchlist_id}")
async def delete_watchlist(
    watchlist_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Delete a watchlist."""
    success = await stock_service.delete_watchlist(db, watchlist_id, user_id)

    if not success:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    return {"status": "deleted", "watchlist_id": watchlist_id}


@router.post("/watchlists/{watchlist_id}/items")
async def add_to_watchlist(
    watchlist_id: int,
    item: WatchlistItemAdd,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Add a stock to a watchlist."""
    # Verify ownership
    watchlist = await stock_service.get_watchlist(db, watchlist_id, user_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    result = await stock_service.add_to_watchlist(
        db, watchlist_id, item.symbol, item.notes
    )

    if not result:
        raise HTTPException(
            status_code=400, detail=f"Could not add {item.symbol} to watchlist"
        )

    return {"status": "added", "stock_id": result.id}


@router.delete("/watchlists/{watchlist_id}/items/{stock_id}")
async def remove_from_watchlist(
    watchlist_id: int,
    stock_id: int,
    user_id: int = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Remove a stock from a watchlist."""
    # Verify ownership
    watchlist = await stock_service.get_watchlist(db, watchlist_id, user_id)
    if not watchlist:
        raise HTTPException(status_code=404, detail="Watchlist not found")

    success = await stock_service.remove_from_watchlist(db, watchlist_id, stock_id)

    if not success:
        raise HTTPException(status_code=404, detail="Item not found in watchlist")

    return {"status": "removed"}