from __future__ import annotations

from domains.analytics.repository import AnalyticsRepository
from domains.analytics.schemas import SignalResultMetricsResponse


class SignalResultsReadModelService:
    def __init__(self, repository: AnalyticsRepository) -> None:
        self.repository = repository

    async def build_signal_results_view(self, window_hours: int = 24) -> SignalResultMetricsResponse:
        return SignalResultMetricsResponse(**(await self.repository.query_signal_results(window_hours)))