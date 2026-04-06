"""
Data source service - Yahoo Finance and Binance integration.
"""
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import aiohttp
import redis.asyncio as redis
from infra.config import settings


@dataclass
class StockQuote:
    """Stock quote data."""
    symbol: str
    name: str
    price: float
    change: float
    change_percent: float
    volume: int
    market_cap: Optional[float]
    previous_close: float
    open: float
    high: float
    low: float
    timestamp: datetime


@dataclass
class StockSearchResult:
    """Stock search result."""
    symbol: str
    name: str
    exchange: str
    type: str  # stock, etf, etc.


@dataclass
class HistoricalData:
    """Historical stock data point."""
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class DataSource(ABC):
    """Abstract base class for data sources."""

    @abstractmethod
    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Get real-time quote for a symbol."""
        pass

    @abstractmethod
    async def search(self, query: str) -> list[StockSearchResult]:
        """Search for stocks by query."""
        pass

    @abstractmethod
    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> list[HistoricalData]:
        """Get historical data for a symbol."""
        pass


class YahooFinanceDataSource(DataSource):
    """Yahoo Finance data source using yfinance-like API."""

    def __init__(self):
        self.base_url = "https://query1.finance.yahoo.com/v8/finance"
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Optional[redis.Redis] = None
        self.cache_ttl = 30  # 30 seconds cache

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_cache(self) -> redis.Redis:
        if self._cache is None:
            self._cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._cache

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Get quote from Yahoo Finance."""
        cache = await self._get_cache()
        cache_key = f"stock:quote:{symbol.upper()}"

        # Check cache first
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

        session = await self._get_session()
        url = f"{self.base_url}/chart/{symbol.upper()}"

        try:
            async with session.get(
                url,
                params={"interval": "1d", "range": "1d"},
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()
                result = data.get("chart", {}).get("result", [])

                if not result:
                    return None

                meta = result[0].get("meta", {})
                indicators = result[0].get("indicators", {}).get("quote", [{}])[0]

                price = meta.get("regularMarketPrice", 0)
                prev_close = meta.get("previousClose", meta.get("chartPreviousClose", 0))
                change = price - prev_close
                change_percent = (change / prev_close * 100) if prev_close else 0

                quote = StockQuote(
                    symbol=meta.get("symbol", symbol.upper()),
                    name=meta.get("shortName", meta.get("longName", symbol)),
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    volume=meta.get("regularMarketVolume", 0),
                    market_cap=meta.get("marketCap"),
                    previous_close=prev_close,
                    open=meta.get("regularMarketOpen", 0),
                    high=meta.get("regularMarketDayHigh", 0),
                    low=meta.get("regularMarketDayLow", 0),
                    timestamp=datetime.utcnow(),
                )

                # Cache the result
                import json
                await cache.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(
                        {
                            "symbol": quote.symbol,
                            "name": quote.name,
                            "price": quote.price,
                            "change": quote.change,
                            "change_percent": quote.change_percent,
                            "volume": quote.volume,
                            "market_cap": quote.market_cap,
                            "previous_close": quote.previous_close,
                            "open": quote.open,
                            "high": quote.high,
                            "low": quote.low,
                            "timestamp": quote.timestamp.isoformat(),
                        }
                    ),
                )

                return quote

        except Exception as e:
            print(f"Yahoo Finance error for {symbol}: {e}")
            return None

    async def search(self, query: str) -> list[StockSearchResult]:
        """Search for stocks using Yahoo Finance."""
        session = await self._get_session()
        url = f"{self.base_url}/search"

        try:
            async with session.get(
                url,
                params={"q": query, "quotesCount": 10, "newsCount": 0},
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                quotes = data.get("quotes", [])

                results = []
                for q in quotes:
                    if q.get("quoteType") in ["EQUITY", "ETF"]:
                        results.append(
                            StockSearchResult(
                                symbol=q.get("symbol", ""),
                                name=q.get("shortname", q.get("longname", "")),
                                exchange=q.get("exchange", "UNKNOWN"),
                                type=q.get("quoteType", "EQUITY").lower(),
                            )
                        )

                return results

        except Exception as e:
            print(f"Yahoo Finance search error: {e}")
            return []

    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> list[HistoricalData]:
        """Get historical data from Yahoo Finance."""
        session = await self._get_session()

        # Map period to Yahoo range
        period_map = {
            "1d": "1d",
            "5d": "5d",
            "1mo": "1mo",
            "3mo": "3mo",
            "6mo": "6mo",
            "1y": "1y",
            "2y": "2y",
            "5y": "5y",
            "max": "max",
        }
        yahoo_range = period_map.get(period, "1mo")

        url = f"{self.base_url}/chart/{symbol.upper()}"

        try:
            async with session.get(
                url,
                params={"interval": "1d", "range": yahoo_range},
                headers={"User-Agent": "Mozilla/5.0"},
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                result = data.get("chart", {}).get("result", [])

                if not result:
                    return []

                timestamps = result[0].get("timestamp", [])
                quote = result[0].get("indicators", {}).get("quote", [{}])[0]

                history = []
                for i, ts in enumerate(timestamps):
                    history.append(
                        HistoricalData(
                            date=datetime.fromtimestamp(ts),
                            open=quote.get("open", [0])[i] or 0,
                            high=quote.get("high", [0])[i] or 0,
                            low=quote.get("low", [0])[i] or 0,
                            close=quote.get("close", [0])[i] or 0,
                            volume=quote.get("volume", [0])[i] or 0,
                        )
                    )

                return history

        except Exception as e:
            print(f"Yahoo Finance historical error for {symbol}: {e}")
            return []


class BinanceDataSource(DataSource):
    """Binance data source for crypto prices."""

    def __init__(self):
        self.base_url = "https://api.binance.com/api/v3"
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Optional[redis.Redis] = None
        self.cache_ttl = 10  # 10 seconds cache for crypto

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_cache(self) -> redis.Redis:
        if self._cache is None:
            self._cache = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._cache

    async def get_quote(self, symbol: str) -> Optional[StockQuote]:
        """Get real-time quote from Binance."""
        # Convert to Binance format (e.g., BTCUSDT)
        symbol = symbol.upper().replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        cache = await self._get_cache()
        cache_key = f"crypto:quote:{symbol}"

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
                market_cap=None,
                previous_close=data["previous_close"],
                open=data["open"],
                high=data["high"],
                low=data["low"],
                timestamp=datetime.fromisoformat(data["timestamp"]),
            )

        session = await self._get_session()

        try:
            # Get 24hr stats
            async with session.get(
                f"{self.base_url}/ticker/24hr",
                params={"symbol": symbol},
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()

                price = float(data.get("lastPrice", 0))
                prev_price = float(data.get("prevClosePrice", price))
                change = price - prev_price
                change_percent = float(data.get("priceChangePercent", 0))

                quote = StockQuote(
                    symbol=symbol,
                    name=symbol,  # Crypto doesn't have company names
                    price=price,
                    change=change,
                    change_percent=change_percent,
                    volume=int(data.get("volume", 0)),
                    market_cap=None,
                    previous_close=prev_price,
                    open=float(data.get("openPrice", 0)),
                    high=float(data.get("highPrice", 0)),
                    low=float(data.get("lowPrice", 0)),
                    timestamp=datetime.utcnow(),
                )

                # Cache result
                import json
                await cache.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(
                        {
                            "symbol": quote.symbol,
                            "name": quote.name,
                            "price": quote.price,
                            "change": quote.change,
                            "change_percent": quote.change_percent,
                            "volume": quote.volume,
                            "market_cap": quote.market_cap,
                            "previous_close": quote.previous_close,
                            "open": quote.open,
                            "high": quote.high,
                            "low": quote.low,
                            "timestamp": quote.timestamp.isoformat(),
                        }
                    ),
                )

                return quote

        except Exception as e:
            print(f"Binance error for {symbol}: {e}")
            return None

    async def search(self, query: str) -> list[StockSearchResult]:
        """Search Binance for crypto symbols."""
        session = await self._get_session()
        query_upper = query.upper()

        try:
            # Get all tickers and filter
            async with session.get(
                f"{self.base_url}/ticker/24hr",
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                results = []
                query_lower = query_lower = query_lower = query.lower()
                for ticker in data:
                    symbol = ticker.get("symbol", "")
                    if query_upper in symbol and symbol.endswith("USDT"):
                        results.append(
                            StockSearchResult(
                                symbol=symbol,
                                name=symbol,
                                exchange="BINANCE",
                                type="crypto",
                            )
                        )
                        if len(results) >= 10:
                            break

                return results

        except Exception as e:
            print(f"Binance search error: {e}")
            return []

    async def get_historical(
        self, symbol: str, period: str = "1mo"
    ) -> list[HistoricalData]:
        """Get historical klines from Binance."""
        symbol = symbol.upper().replace("-", "")
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        # Map period to Binance interval
        interval_map = {
            "1d": "1d",
            "5d": "1d",
            "1mo": "1d",
            "3mo": "1d",
            "6mo": "1w",
            "1y": "1w",
            "2y": "1w",
            "5y": "1M",
            "max": "1M",
        }
        interval = interval_map.get(period, "1d")

        # Map period to limit
        limit_map = {
            "1d": 1,
            "5d": 5,
            "1mo": 30,
            "3mo": 90,
            "6mo": 180,
            "1y": 365,
            "2y": 730,
            "5y": 1825,
            "max": 1825,
        }
        limit = limit_map.get(period, 30)

        session = await self._get_session()

        try:
            async with session.get(
                f"{self.base_url}/klines",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                },
            ) as response:
                if response.status != 200:
                    return []

                data = await response.json()

                history = []
                for kline in data:
                    history.append(
                        HistoricalData(
                            date=datetime.fromtimestamp(kline[0] / 1000),
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=int(kline[5]),
                        )
                    )

                return history

        except Exception as e:
            print(f"Binance historical error for {symbol}: {e}")
            return []


# Factory for creating data sources
class DataSourceFactory:
    """Factory for creating data source instances."""

    _sources: dict[str, DataSource] = {}

    @classmethod
    def get_source(cls, source_type: str) -> DataSource:
        """Get a data source instance by type."""
        if source_type not in cls._sources:
            if source_type == "yahoo":
                cls._sources[source_type] = YahooFinanceDataSource()
            elif source_type == "binance":
                cls._sources[source_type] = BinanceDataSource()
            else:
                raise ValueError(f"Unknown data source: {source_type}")

        return cls._sources[source_type]

    @classmethod
    async def get_quote(cls, symbol: str, source: str = "yahoo") -> Optional[StockQuote]:
        """Get quote from specified source."""
        return await cls.get_source(source).get_quote(symbol)

    @classmethod
    async def search(cls, query: str, source: str = "yahoo") -> list[StockSearchResult]:
        """Search using specified source."""
        return await cls.get_source(source).search(query)

    @classmethod
    async def get_historical(
        cls, symbol: str, period: str = "1mo", source: str = "yahoo"
    ) -> list[HistoricalData]:
        """Get historical data from specified source."""
        return await cls.get_source(source).get_historical(symbol, period)