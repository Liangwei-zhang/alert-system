from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from domains.market_data.proxy_service import MarketDataProxyService

router = APIRouter(prefix="/market", tags=["market-data"])

_ALLOWED_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"}
_ALLOWED_SOURCES = {"auto", "yahoo", "binance"}


class MarketChartBarResponse(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketChartQuoteResponse(BaseModel):
    latest_at: datetime | None = None
    latest_close: float = 0.0
    previous_close: float = 0.0
    change: float = 0.0
    change_pct: float = 0.0
    session_open: float = 0.0
    session_high: float = 0.0
    session_low: float = 0.0
    session_volume: int = 0


class MarketChartResponse(BaseModel):
    source: str
    symbol: str
    asset_type: str | None = None
    period: str
    bars: list[MarketChartBarResponse]
    quote: MarketChartQuoteResponse


def _market_data_service() -> MarketDataProxyService:
    return MarketDataProxyService()


def _normalize_period(period: str) -> str:
    normalized = str(period or "1mo").strip().lower()
    return normalized if normalized in _ALLOWED_PERIODS else "1mo"


def _resolve_source(symbol: str, source: str, asset_type: str | None) -> str:
    normalized_source = str(source or "auto").strip().lower()
    if normalized_source not in _ALLOWED_SOURCES:
        normalized_source = "auto"
    if normalized_source != "auto":
        return normalized_source

    normalized_symbol = str(symbol or "").strip().upper()
    normalized_asset_type = str(asset_type or "").strip().lower()
    if normalized_asset_type == "crypto" or normalized_symbol.endswith("USDT"):
        return "binance"
    return "yahoo"


def _build_quote(bars: list[dict]) -> MarketChartQuoteResponse:
    if not bars:
        return MarketChartQuoteResponse()

    latest = bars[-1]
    previous = bars[-2] if len(bars) > 1 else bars[-1]
    latest_close = float(latest.get("close") or 0.0)
    previous_close = float(previous.get("close") or 0.0)
    change = latest_close - previous_close
    change_pct = (change / previous_close * 100.0) if previous_close else 0.0
    return MarketChartQuoteResponse(
        latest_at=latest.get("date"),
        latest_close=latest_close,
        previous_close=previous_close,
        change=change,
        change_pct=change_pct,
        session_open=float(latest.get("open") or 0.0),
        session_high=float(latest.get("high") or 0.0),
        session_low=float(latest.get("low") or 0.0),
        session_volume=int(latest.get("volume") or 0),
    )


@router.get("/chart/{symbol}", response_model=MarketChartResponse)
async def get_market_chart(
    symbol: str,
    period: str = Query(default="3mo"),
    source: str = Query(default="auto"),
    asset_type: str | None = Query(default=None),
    service: MarketDataProxyService = Depends(_market_data_service),
) -> MarketChartResponse:
    normalized_symbol = str(symbol or "").strip().upper()
    resolved_source = _resolve_source(normalized_symbol, source, asset_type)
    normalized_period = _normalize_period(period)
    payload = await service.get_historical(
        source=resolved_source,
        symbol=normalized_symbol,
        period=normalized_period,
    )
    bars = payload.get("bars") or []
    return MarketChartResponse(
        source=resolved_source,
        symbol=normalized_symbol,
        asset_type=str(asset_type or "").strip().lower() or None,
        period=normalized_period,
        bars=[MarketChartBarResponse(**item) for item in bars],
        quote=_build_quote(bars),
    )