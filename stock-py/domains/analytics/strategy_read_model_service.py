from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import StrategyHealthResponse


class StrategyReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_strategy_health_view(self, window_hours: int = 168) -> StrategyHealthResponse:
        return StrategyHealthResponse(**(await self.repository.query_strategy_health(window_hours)))
