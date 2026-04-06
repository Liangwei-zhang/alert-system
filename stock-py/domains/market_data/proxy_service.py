from __future__ import annotations

from typing import Any

from infra.market_data.data_source import HistoricalBar, MarketDataSourceFactory


class MarketDataProxyService:
    async def get_historical(
        self,
        *,
        source: str,
        symbol: str,
        period: str = "1mo",
    ) -> dict[str, Any]:
        normalized_source = str(source).strip().lower()
        normalized_symbol = str(symbol).strip().upper()
        bars = await MarketDataSourceFactory.get_historical(
            normalized_symbol,
            period,
            source=normalized_source,
        )
        return {
            "source": normalized_source,
            "symbol": normalized_symbol,
            "period": period,
            "bars": [self._serialize_bar(bar) for bar in bars],
        }

    @staticmethod
    def _serialize_bar(bar: HistoricalBar) -> dict[str, Any]:
        return {
            "date": bar.date,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": int(bar.volume),
        }