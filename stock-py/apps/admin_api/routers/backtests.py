from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.dependencies import get_analytics_repository
from domains.analytics.backtest.repository import BacktestRepository
from domains.analytics.backtest.service import BacktestService
from domains.analytics.repository import AnalyticsRepository
from domains.signals.calibration_feedback_loop_service import CalibrationFeedbackLoopService
from domains.signals.calibration_repository import SignalCalibrationSnapshotRepository
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/backtests", tags=["admin", "backtests"])


class AdminBacktestRunResponse(BaseModel):
    id: int
    strategy_name: str
    experiment_name: str | None = None
    run_key: str | None = None
    symbol: str | None = None
    timeframe: str
    window_days: int
    status: str
    summary: dict[str, Any] | list[Any] | None = None
    config: dict[str, Any] | list[Any] | None = None
    metrics: dict[str, Any] | list[Any] | None = None
    evidence: dict[str, Any] | list[Any] | None = None
    artifacts: dict[str, Any] | list[Any] | None = None
    code_version: str | None = None
    dataset_fingerprint: str | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AdminBacktestRunListResponse(BaseModel):
    data: list[AdminBacktestRunResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AdminBacktestTradeResponse(BaseModel):
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    return_percent: float


class AdminBacktestEquityPointResponse(BaseModel):
    timestamp: datetime
    equity: float
    drawdown_percent: float = 0.0


class AdminBacktestEquityCurveResponse(BaseModel):
    symbol: str
    strategy_name: str
    timeframe: str
    window_days: int
    metrics: dict[str, Any] | list[Any] | None = None
    trades: list[AdminBacktestTradeResponse] = Field(default_factory=list)
    equity_points: list[float] = Field(default_factory=list)
    equity_series: list[AdminBacktestEquityPointResponse] = Field(default_factory=list)


class AdminBacktestRankingResponse(BaseModel):
    id: int | None = None
    strategy_name: str
    timeframe: str
    rank: int
    score: float
    degradation: float
    symbols_covered: int
    evidence: dict[str, Any] | list[Any] | None = None
    as_of_date: datetime | None = None


class AdminBacktestRankingListResponse(BaseModel):
    as_of_date: datetime | None = None
    data: list[AdminBacktestRankingResponse]
    limit: int


class TriggerBacktestRefreshRequest(BaseModel):
    symbols: list[str] | None = Field(default=None)
    strategy_names: list[str] | None = Field(default=None)
    windows: list[int] | None = Field(default=None)
    timeframe: str = Field(default="1d", min_length=1, max_length=16)
    experiment_name: str | None = Field(default=None, min_length=1, max_length=120)
    auto_feedback_loop: bool = True
    activate_feedback_snapshot: bool = True
    feedback_signal_window_hours: int = Field(default=24, ge=1, le=24 * 30)
    feedback_ranking_window_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)


class AdminBacktestCalibrationFeedbackResponse(BaseModel):
    generated_at: datetime
    applied_version: str
    previous_version: str | None = None
    activated: bool
    effective_from: datetime | None = None
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    score_multipliers: dict[str, float] = Field(default_factory=dict)
    atr_multipliers: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class TriggerBacktestRefreshResponse(BaseModel):
    run_id: int
    experiment_name: str | None = None
    run_key: str | None = None
    code_version: str | None = None
    dataset_fingerprint: str | None = None
    ranking_count: int
    rankings: list[AdminBacktestRankingResponse]
    calibration_feedback: AdminBacktestCalibrationFeedbackResponse | None = None
    calibration_feedback_error: str | None = None


def _load_payload(value: str | None) -> dict[str, Any] | list[Any] | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {"raw": value}
    if isinstance(payload, (dict, list)):
        return payload
    return {"value": payload}


def _run_to_response(run: Any) -> AdminBacktestRunResponse:
    return AdminBacktestRunResponse(
        id=int(run.id),
        strategy_name=str(run.strategy_name),
        experiment_name=getattr(run, "experiment_name", None),
        run_key=getattr(run, "run_key", None),
        symbol=str(run.symbol) if getattr(run, "symbol", None) else None,
        timeframe=str(run.timeframe),
        window_days=int(run.window_days or 0),
        status=str(getattr(run.status, "value", run.status)),
        summary=_load_payload(getattr(run, "summary", None)),
        config=_load_payload(getattr(run, "config", None)),
        metrics=_load_payload(getattr(run, "metrics", None)),
        evidence=_load_payload(getattr(run, "evidence", None)),
        artifacts=_load_payload(getattr(run, "artifacts", None)),
        code_version=getattr(run, "code_version", None),
        dataset_fingerprint=getattr(run, "dataset_fingerprint", None),
        error_message=getattr(run, "error_message", None),
        started_at=run.started_at,
        completed_at=getattr(run, "completed_at", None),
    )


def _ranking_to_response(ranking: Any) -> AdminBacktestRankingResponse:
    return AdminBacktestRankingResponse(
        id=int(ranking.id) if getattr(ranking, "id", None) is not None else None,
        strategy_name=str(ranking.strategy_name),
        timeframe=str(ranking.timeframe),
        rank=int(ranking.rank),
        score=float(ranking.score),
        degradation=float(ranking.degradation),
        symbols_covered=int(ranking.symbols_covered or 0),
        evidence=_load_payload(getattr(ranking, "evidence", None)),
        as_of_date=getattr(ranking, "as_of_date", None),
    )


def _ranking_payload_to_response(ranking: dict[str, Any]) -> AdminBacktestRankingResponse:
    return AdminBacktestRankingResponse(
        strategy_name=str(ranking["strategy_name"]),
        timeframe=str(ranking.get("timeframe") or "1d"),
        rank=int(ranking.get("rank") or 0),
        score=float(ranking.get("score") or 0.0),
        degradation=float(ranking.get("degradation") or 0.0),
        symbols_covered=int(ranking.get("symbols_covered") or 0),
        evidence=ranking.get("evidence"),
    )


@router.get("", response_model=dict)
async def get_backtests_root() -> dict[str, object]:
    return {
        "areas": ["runs", "rankings", "equity-curve"],
        "actions": [
            "runs:list",
            "runs:get",
            "runs:create",
            "rankings:list-latest",
            "equity-curve:get",
        ],
    }


@router.get("/equity-curve", response_model=AdminBacktestEquityCurveResponse)
async def get_equity_curve(
    symbol: str = Query(..., min_length=1, description="Ticker symbol"),
    strategy_name: str = Query(..., min_length=1, description="Backtest strategy name or alias"),
    window_days: int = Query(90, ge=20, le=3650, description="Backtest lookback window in days"),
    timeframe: str = Query("1d", min_length=1, max_length=16, description="Timeframe"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminBacktestEquityCurveResponse:
    service = BacktestService(db)
    result = await service.run_backtest_window(
        symbol=symbol,
        strategy_name=strategy_name,
        window_days=window_days,
        timeframe=timeframe,
    )
    if result is None:
        raise AppError(
            code="backtest_equity_curve_unavailable",
            message="Backtest equity curve unavailable for the requested input",
            status_code=404,
        )
    return AdminBacktestEquityCurveResponse(
        symbol=str(result["symbol"]),
        strategy_name=str(result["strategy_name"]),
        timeframe=str(result["timeframe"]),
        window_days=int(result["window_days"]),
        metrics=result.get("metrics"),
        trades=[AdminBacktestTradeResponse(**trade) for trade in list(result.get("trades") or [])],
        equity_points=[float(value) for value in list(result.get("equity_points") or [])],
        equity_series=[
            AdminBacktestEquityPointResponse(**point)
            for point in list(result.get("equity_series") or [])
            if isinstance(point, dict)
        ],
    )


@router.get("/runs", response_model=AdminBacktestRunListResponse)
async def list_runs(
    status: str | None = Query(
        None,
        pattern="^(pending|running|completed|failed)$",
        description="Filter by run status",
    ),
    strategy_name: str | None = Query(None, description="Filter by strategy name"),
    experiment_name: str | None = Query(None, description="Filter by experiment name"),
    run_key: str | None = Query(None, description="Filter by run key"),
    timeframe: str | None = Query(None, description="Filter by timeframe"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminBacktestRunListResponse:
    repository = BacktestRepository(db)
    runs = await repository.list_runs(
        limit=limit,
        offset=offset,
        status=status,
        strategy_name=strategy_name,
        experiment_name=experiment_name,
        run_key=run_key,
        timeframe=timeframe,
        symbol=symbol,
    )
    total = await repository.count_runs(
        status=status,
        strategy_name=strategy_name,
        experiment_name=experiment_name,
        run_key=run_key,
        timeframe=timeframe,
        symbol=symbol,
    )
    return AdminBacktestRunListResponse(
        data=[_run_to_response(run) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(runs)) < total,
    )


@router.get("/runs/{run_id}", response_model=AdminBacktestRunResponse)
async def get_run(
    run_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> AdminBacktestRunResponse:
    run = await BacktestRepository(db).get_run(run_id)
    if run is None:
        raise AppError(
            code="backtest_run_not_found",
            message="Backtest run not found",
            status_code=404,
        )
    return _run_to_response(run)


@router.get("/rankings/latest", response_model=AdminBacktestRankingListResponse)
async def list_latest_rankings(
    timeframe: str | None = Query(None, description="Filter by timeframe"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminBacktestRankingListResponse:
    rankings = await BacktestRepository(db).list_latest_rankings(timeframe=timeframe, limit=limit)
    return AdminBacktestRankingListResponse(
        as_of_date=rankings[0].as_of_date if rankings else None,
        data=[_ranking_to_response(ranking) for ranking in rankings],
        limit=limit,
    )


@router.post("/runs", response_model=TriggerBacktestRefreshResponse)
async def create_run(
    request: TriggerBacktestRefreshRequest,
    db: AsyncSession = Depends(get_db_session),
    analytics_repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> TriggerBacktestRefreshResponse:
    result = await BacktestService(db).refresh_rankings(
        symbols=request.symbols,
        strategy_names=request.strategy_names,
        windows=request.windows,
        timeframe=request.timeframe,
        experiment_name=request.experiment_name,
        experiment_context={
            "trigger": "admin_api",
            "entrypoint": "apps.admin_api.routers.backtests.create_run",
            "dataset": {
                "selection_mode": "request",
            },
        },
    )
    rankings = [
        _ranking_payload_to_response(ranking)
        for ranking in list(result.get("rankings") or [])
        if isinstance(ranking, dict)
    ]
    feedback_payload = None
    feedback_error = None
    if request.auto_feedback_loop:
        try:
            feedback_payload = await CalibrationFeedbackLoopService(
                analytics_repository=analytics_repository,
                calibration_repository=SignalCalibrationSnapshotRepository(db),
            ).create_feedback_snapshot(
                run_id=int(result.get("run_id") or 0) or None,
                timeframe=request.timeframe,
                signal_window_hours=request.feedback_signal_window_hours,
                ranking_window_hours=request.feedback_ranking_window_hours,
                activate=request.activate_feedback_snapshot,
                experiment_name=result.get("experiment_name"),
            )
        except Exception as exc:  # pragma: no cover - non-fatal guardrail around the feedback loop
            feedback_error = str(exc)
    return TriggerBacktestRefreshResponse(
        run_id=int(result.get("run_id") or 0),
        experiment_name=result.get("experiment_name"),
        run_key=result.get("run_key"),
        code_version=result.get("code_version"),
        dataset_fingerprint=result.get("dataset_fingerprint"),
        ranking_count=int(result.get("ranking_count") or len(rankings)),
        rankings=rankings,
        calibration_feedback=(
            AdminBacktestCalibrationFeedbackResponse(**feedback_payload)
            if isinstance(feedback_payload, dict)
            else None
        ),
        calibration_feedback_error=feedback_error,
    )
