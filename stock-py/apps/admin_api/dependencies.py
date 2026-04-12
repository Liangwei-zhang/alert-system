from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from domains.analytics.distribution_read_model_service import DistributionReadModelService
from domains.analytics.overview_read_model_service import OverviewReadModelService
from domains.analytics.repository import AnalyticsRepository
from domains.analytics.signal_results_read_model_service import SignalResultsReadModelService
from domains.analytics.strategy_read_model_service import StrategyReadModelService
from domains.analytics.tradingagents_read_model_service import TradingAgentsReadModelService
from domains.tradingagents.repository import TradingAgentsRepository
from infra.analytics.clickhouse_client import ClickHouseClient, get_clickhouse_client
from infra.db.session import get_db_session


async def get_tradingagents_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TradingAgentsRepository:
    return TradingAgentsRepository(session)


async def get_clickhouse_analytics_client() -> ClickHouseClient:
    return get_clickhouse_client()


async def get_analytics_repository(
    client: ClickHouseClient = Depends(get_clickhouse_analytics_client),
) -> AnalyticsRepository:
    return AnalyticsRepository(client)


async def get_overview_read_model_service(
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> OverviewReadModelService:
    return OverviewReadModelService(repository)


async def get_distribution_read_model_service(
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> DistributionReadModelService:
    return DistributionReadModelService(repository)


async def get_strategy_read_model_service(
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> StrategyReadModelService:
    return StrategyReadModelService(repository)


async def get_signal_results_read_model_service(
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> SignalResultsReadModelService:
    return SignalResultsReadModelService(repository)


async def get_tradingagents_read_model_service(
    repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> TradingAgentsReadModelService:
    return TradingAgentsReadModelService(repository)
