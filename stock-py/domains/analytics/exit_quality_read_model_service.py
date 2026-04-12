from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import ExitQualityMetricsResponse


class ExitQualityReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_exit_quality_view(self, window_hours: int = 24) -> ExitQualityMetricsResponse:
        return ExitQualityMetricsResponse(**(await self.repository.query_exit_quality(window_hours)))