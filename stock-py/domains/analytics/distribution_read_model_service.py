from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import DistributionMetricsResponse


class DistributionReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_distribution_view(self, window_hours: int = 24) -> DistributionMetricsResponse:
        return DistributionMetricsResponse(
            **(await self.repository.query_distribution(window_hours))
        )
