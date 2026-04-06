from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import OverviewMetricsResponse


class OverviewReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_dashboard(self, window_hours: int = 24) -> OverviewMetricsResponse:
        return OverviewMetricsResponse(**(await self.repository.query_overview(window_hours)))
