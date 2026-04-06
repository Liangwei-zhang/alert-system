from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.analytics.backtest.repository import BacktestRepository
from domains.analytics.backtest.service import BacktestService
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/backtests", tags=["admin", "backtests"])


class AdminBacktestRunResponse(BaseModel):
    id: int
    strategy_name: str
    symbol: str | None = None
    timeframe: str
    window_days: int
    status: str
    summary: dict[str, Any] | list[Any] | None = None
    metrics: dict[str, Any] | list[Any] | None = None
    evidence: dict[str, Any] | list[Any] | None = None
    error_message: str | None = None
    started_at: datetime
    completed_at: datetime | None = None


class AdminBacktestRunListResponse(BaseModel):
    data: list[AdminBacktestRunResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


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


class TriggerBacktestRefreshResponse(BaseModel):
    run_id: int
    ranking_count: int
    rankings: list[AdminBacktestRankingResponse]


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
        symbol=str(run.symbol) if getattr(run, "symbol", None) else None,
        timeframe=str(run.timeframe),
        window_days=int(run.window_days or 0),
        status=str(getattr(run.status, "value", run.status)),
        summary=_load_payload(getattr(run, "summary", None)),
        metrics=_load_payload(getattr(run, "metrics", None)),
        evidence=_load_payload(getattr(run, "evidence", None)),
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
        "areas": ["runs", "rankings"],
        "actions": ["runs:list", "runs:get", "runs:create", "rankings:list-latest"],
    }


@router.get("/runs", response_model=AdminBacktestRunListResponse)
async def list_runs(
    status: str | None = Query(
        None,
        pattern="^(pending|running|completed|failed)$",
        description="Filter by run status",
    ),
    strategy_name: str | None = Query(None, description="Filter by strategy name"),
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
        timeframe=timeframe,
        symbol=symbol,
    )
    total = await repository.count_runs(
        status=status,
        strategy_name=strategy_name,
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
) -> TriggerBacktestRefreshResponse:
    result = await BacktestService(db).refresh_rankings(
        symbols=request.symbols,
        strategy_names=request.strategy_names,
        windows=request.windows,
        timeframe=request.timeframe,
    )
    rankings = [
        _ranking_payload_to_response(ranking)
        for ranking in list(result.get("rankings") or [])
        if isinstance(ranking, dict)
    ]
    return TriggerBacktestRefreshResponse(
        run_id=int(result.get("run_id") or 0),
        ranking_count=int(result.get("ranking_count") or len(rankings)),
        rankings=rankings,
    )
