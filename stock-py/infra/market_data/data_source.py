from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone

from infra.http.http_client import get_http_client_factory


@dataclass(slots=True)
class SymbolSearchResult:
    symbol: str
    name: str
    exchange: str
    type: str


@dataclass(slots=True)
class HistoricalBar:
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataSource(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[SymbolSearchResult]:
        raise NotImplementedError

    @abstractmethod
    async def get_historical(self, symbol: str, period: str = "1mo") -> list[HistoricalBar]:
        raise NotImplementedError


class YahooFinanceDataSource(MarketDataSource):
    search_url = "https://query1.finance.yahoo.com/v1/finance/search"
    chart_base_url = "https://query1.finance.yahoo.com/v8/finance/chart"

    async def search(self, query: str) -> list[SymbolSearchResult]:
        client = await get_http_client_factory().get_external_client()
        response = await client.get(
            self.search_url,
            params={"q": query, "quotesCount": 10, "newsCount": 0},
        )
        if response.status_code != 200:
            return []

        payload = response.json()
        results: list[SymbolSearchResult] = []
        for item in payload.get("quotes", []):
            quote_type = str(item.get("quoteType") or "").upper()
            if quote_type not in {"EQUITY", "ETF"}:
                continue
            symbol = str(item.get("symbol") or "").strip().upper()
            if not symbol:
                continue
            results.append(
                SymbolSearchResult(
                    symbol=symbol,
                    name=str(item.get("shortname") or item.get("longname") or symbol),
                    exchange=str(item.get("exchange") or "UNKNOWN"),
                    type=quote_type.lower(),
                )
            )
        return results

    async def get_historical(self, symbol: str, period: str = "1mo") -> list[HistoricalBar]:
        client = await get_http_client_factory().get_external_client()
        response = await client.get(
            f"{self.chart_base_url}/{symbol.upper()}",
            params={"interval": "1d", "range": self._normalize_period(period)},
        )
        if response.status_code != 200:
            return []

        payload = response.json()
        results = payload.get("chart", {}).get("result", [])
        if not results:
            return []

        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = (result.get("indicators") or {}).get("quote", [{}])[0]
        bars: list[HistoricalBar] = []
        for index, raw_timestamp in enumerate(timestamps):
            bars.append(
                HistoricalBar(
                    date=datetime.fromtimestamp(raw_timestamp, tz=timezone.utc),
                    open=float((quote.get("open") or [0])[index] or 0),
                    high=float((quote.get("high") or [0])[index] or 0),
                    low=float((quote.get("low") or [0])[index] or 0),
                    close=float((quote.get("close") or [0])[index] or 0),
                    volume=int((quote.get("volume") or [0])[index] or 0),
                )
            )
        return bars

    @staticmethod
    def _normalize_period(period: str) -> str:
        return {
            "1d": "1d",
            "5d": "5d",
            "1mo": "1mo",
            "3mo": "3mo",
            "6mo": "6mo",
            "1y": "1y",
            "2y": "2y",
            "5y": "5y",
            "max": "max",
        }.get(period, "1mo")


class BinanceDataSource(MarketDataSource):
    base_url = "https://api.binance.com/api/v3"

    async def search(self, query: str) -> list[SymbolSearchResult]:
        client = await get_http_client_factory().get_external_client()
        response = await client.get(f"{self.base_url}/ticker/24hr")
        if response.status_code != 200:
            return []

        results: list[SymbolSearchResult] = []
        query_upper = query.upper()
        for ticker in response.json():
            symbol = str(ticker.get("symbol") or "").upper()
            if query_upper not in symbol or not symbol.endswith("USDT"):
                continue
            results.append(
                SymbolSearchResult(
                    symbol=symbol,
                    name=symbol,
                    exchange="BINANCE",
                    type="crypto",
                )
            )
            if len(results) >= 10:
                break
        return results

    async def get_historical(self, symbol: str, period: str = "1mo") -> list[HistoricalBar]:
        normalized_symbol = symbol.upper().replace("-", "")
        if not normalized_symbol.endswith("USDT"):
            normalized_symbol = f"{normalized_symbol}USDT"

        interval, limit = self._normalize_period(period)
        client = await get_http_client_factory().get_external_client()
        response = await client.get(
            f"{self.base_url}/klines",
            params={"symbol": normalized_symbol, "interval": interval, "limit": limit},
        )
        if response.status_code != 200:
            return []

        bars: list[HistoricalBar] = []
        for row in response.json():
            bars.append(
                HistoricalBar(
                    date=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=int(float(row[5])),
                )
            )
        return bars

    @staticmethod
    def _normalize_period(period: str) -> tuple[str, int]:
        return {
            "1d": ("1d", 1),
            "5d": ("1d", 5),
            "1mo": ("1d", 30),
            "3mo": ("1d", 90),
            "6mo": ("1w", 180),
            "1y": ("1w", 365),
            "2y": ("1w", 730),
            "5y": ("1M", 1825),
            "max": ("1M", 1825),
        }.get(period, ("1d", 30))


class MarketDataSourceFactory:
    _sources: dict[str, MarketDataSource] = {}

    @classmethod
    def get_source(cls, source_type: str) -> MarketDataSource:
        normalized = source_type.lower().strip()
        if normalized not in cls._sources:
            if normalized == "yahoo":
                cls._sources[normalized] = YahooFinanceDataSource()
            elif normalized == "binance":
                cls._sources[normalized] = BinanceDataSource()
            else:
                raise ValueError(f"Unknown data source: {source_type}")
        return cls._sources[normalized]

    @classmethod
    async def search(cls, query: str, source: str = "yahoo") -> list[SymbolSearchResult]:
        return await cls.get_source(source).search(query)

    @classmethod
    async def get_historical(
        cls, symbol: str, period: str = "1mo", source: str = "yahoo"
    ) -> list[HistoricalBar]:
        return await cls.get_source(source).get_historical(symbol, period)
