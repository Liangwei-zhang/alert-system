from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import TradingAgentsMetricsResponse


class TradingAgentsReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_tradingagents_view(
        self, window_hours: int = 24
    ) -> TradingAgentsMetricsResponse:
        return TradingAgentsMetricsResponse(
            **(await self.repository.query_tradingagents_metrics(window_hours))
        )
