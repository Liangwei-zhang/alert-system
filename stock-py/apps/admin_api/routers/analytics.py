from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.admin_api.dependencies import (
    get_distribution_read_model_service,
    get_exit_quality_read_model_service,
    get_overview_read_model_service,
    get_signal_results_read_model_service,
    get_strategy_read_model_service,
    get_tradingagents_read_model_service,
)
from domains.analytics.distribution_read_model_service import DistributionReadModelService
from domains.analytics.exit_quality_read_model_service import ExitQualityReadModelService
from domains.analytics.overview_read_model_service import OverviewReadModelService
from domains.analytics.signal_results_read_model_service import SignalResultsReadModelService
from domains.analytics.schemas import (
    DistributionMetricsResponse,
    ExitQualityMetricsResponse,
    OverviewMetricsResponse,
    SignalResultMetricsResponse,
    StrategyHealthResponse,
    TradingAgentsMetricsResponse,
)
from domains.analytics.strategy_read_model_service import StrategyReadModelService
from domains.analytics.tradingagents_read_model_service import TradingAgentsReadModelService

router = APIRouter(prefix="/v1/admin/analytics", tags=["admin", "analytics"])


@router.get("/overview", response_model=OverviewMetricsResponse)
async def get_overview(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    service: OverviewReadModelService = Depends(get_overview_read_model_service),
) -> OverviewMetricsResponse:
    return await service.build_dashboard(window_hours)


@router.get("/distribution", response_model=DistributionMetricsResponse)
async def get_distribution(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    service: DistributionReadModelService = Depends(get_distribution_read_model_service),
) -> DistributionMetricsResponse:
    return await service.build_distribution_view(window_hours)


@router.get("/strategy-health", response_model=StrategyHealthResponse)
async def get_strategy_health(
    window_hours: int = Query(24 * 7, ge=1, le=24 * 365),
    service: StrategyReadModelService = Depends(get_strategy_read_model_service),
) -> StrategyHealthResponse:
    return await service.build_strategy_health_view(window_hours)


@router.get("/signal-results", response_model=SignalResultMetricsResponse)
async def get_signal_results(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    service: SignalResultsReadModelService = Depends(get_signal_results_read_model_service),
) -> SignalResultMetricsResponse:
    return await service.build_signal_results_view(window_hours)


@router.get("/exit-quality", response_model=ExitQualityMetricsResponse)
async def get_exit_quality(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    service: ExitQualityReadModelService = Depends(get_exit_quality_read_model_service),
) -> ExitQualityMetricsResponse:
    return await service.build_exit_quality_view(window_hours)


@router.get("/tradingagents", response_model=TradingAgentsMetricsResponse)
async def get_tradingagents_metrics(
    window_hours: int = Query(24, ge=1, le=24 * 30),
    service: TradingAgentsReadModelService = Depends(get_tradingagents_read_model_service),
) -> TradingAgentsMetricsResponse:
    return await service.build_tradingagents_view(window_hours)
