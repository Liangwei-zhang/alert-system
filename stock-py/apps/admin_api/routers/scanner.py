from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.repository import ScannerRunRepository
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/scanner", tags=["admin", "scanner"])


class AdminScannerRunResponse(BaseModel):
    id: int
    bucket_id: int
    status: str
    scanned_count: int
    emitted_count: int
    suppressed_count: int
    started_at: datetime
    finished_at: datetime | None = None
    error_message: str | None = None
    duration_seconds: float | None = None


class AdminScannerDecisionResponse(BaseModel):
    id: int
    run_id: int
    symbol: str
    decision: str
    reason: str
    signal_type: str | None = None
    score: float | None = None
    suppressed: bool
    dedupe_key: str | None = None
    created_at: datetime


class AdminScannerObservabilitySummaryResponse(BaseModel):
    total_runs: int
    running_runs: int
    completed_runs: int
    failed_runs: int
    total_decisions: int
    emitted_decisions: int
    suppressed_decisions: int
    skipped_decisions: int
    error_decisions: int


class AdminScannerObservabilityResponse(BaseModel):
    summary: AdminScannerObservabilitySummaryResponse
    runs: list[AdminScannerRunResponse]
    runs_total: int
    limit: int
    offset: int
    has_more: bool
    recent_decisions: list[AdminScannerDecisionResponse]
    decision_limit: int


class AdminScannerRunDetailResponse(BaseModel):
    run: AdminScannerRunResponse
    decisions: list[AdminScannerDecisionResponse]


class AdminLiveDecisionListResponse(BaseModel):
    data: list[AdminScannerDecisionResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


def _run_to_response(run) -> AdminScannerRunResponse:
    duration_seconds = None
    if (
        getattr(run, "finished_at", None) is not None
        and getattr(run, "started_at", None) is not None
    ):
        duration_seconds = round((run.finished_at - run.started_at).total_seconds(), 3)
    return AdminScannerRunResponse(
        id=int(run.id),
        bucket_id=int(run.bucket_id),
        status=str(run.status),
        scanned_count=int(run.scanned_count or 0),
        emitted_count=int(run.emitted_count or 0),
        suppressed_count=int(run.suppressed_count or 0),
        started_at=run.started_at,
        finished_at=getattr(run, "finished_at", None),
        error_message=getattr(run, "error_message", None),
        duration_seconds=duration_seconds,
    )


def _decision_to_response(decision) -> AdminScannerDecisionResponse:
    return AdminScannerDecisionResponse(
        id=int(decision.id),
        run_id=int(decision.run_id),
        symbol=str(decision.symbol),
        decision=str(decision.decision),
        reason=str(decision.reason),
        signal_type=str(decision.signal_type) if getattr(decision, "signal_type", None) else None,
        score=float(decision.score) if getattr(decision, "score", None) is not None else None,
        suppressed=bool(decision.suppressed),
        dedupe_key=str(decision.dedupe_key) if getattr(decision, "dedupe_key", None) else None,
        created_at=decision.created_at,
    )


@router.get("", response_model=dict)
async def get_scanner_root() -> dict[str, object]:
    return {
        "areas": ["observability", "live-decision"],
        "actions": ["observability:list", "observability:get", "live-decision:list"],
    }


@router.get("/observability", response_model=AdminScannerObservabilityResponse)
async def get_observability(
    status: str | None = Query(
        None,
        pattern="^(running|completed|failed)$",
        description="Filter runs by status",
    ),
    bucket_id: int | None = Query(None, ge=0, description="Filter runs by bucket id"),
    symbol: str | None = Query(None, description="Filter recent decisions by symbol"),
    decision: str | None = Query(
        None,
        pattern="^(emitted|suppressed|skipped|error)$",
        description="Filter recent decisions by outcome",
    ),
    limit: int = Query(25, ge=1, le=200, description="Run results limit"),
    offset: int = Query(0, ge=0, description="Run results offset"),
    decision_limit: int = Query(25, ge=1, le=200, description="Recent decision results limit"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminScannerObservabilityResponse:
    repository = ScannerRunRepository(db)
    runs = await repository.list_runs(
        limit=limit, offset=offset, status=status, bucket_id=bucket_id
    )
    runs_total = await repository.count_runs(status=status, bucket_id=bucket_id)
    recent_decisions = await repository.list_decisions(
        limit=decision_limit,
        run_id=None,
        symbol=symbol,
        decision=decision,
    )
    summary = AdminScannerObservabilitySummaryResponse(
        total_runs=runs_total,
        running_runs=await repository.count_runs(status="running", bucket_id=bucket_id),
        completed_runs=await repository.count_runs(status="completed", bucket_id=bucket_id),
        failed_runs=await repository.count_runs(status="failed", bucket_id=bucket_id),
        total_decisions=await repository.count_decisions(symbol=symbol, decision=decision),
        emitted_decisions=await repository.count_decisions(symbol=symbol, decision="emitted"),
        suppressed_decisions=await repository.count_decisions(symbol=symbol, decision="suppressed"),
        skipped_decisions=await repository.count_decisions(symbol=symbol, decision="skipped"),
        error_decisions=await repository.count_decisions(symbol=symbol, decision="error"),
    )
    return AdminScannerObservabilityResponse(
        summary=summary,
        runs=[_run_to_response(run) for run in runs],
        runs_total=runs_total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(runs)) < runs_total,
        recent_decisions=[_decision_to_response(item) for item in recent_decisions],
        decision_limit=decision_limit,
    )


@router.get("/runs/{run_id}", response_model=AdminScannerRunDetailResponse)
async def get_run(
    run_id: int,
    decision_limit: int = Query(200, ge=1, le=500, description="Decision results limit"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminScannerRunDetailResponse:
    repository = ScannerRunRepository(db)
    run = await repository.get_run(run_id)
    if run is None:
        raise AppError(
            code="scanner_run_not_found",
            message="Scanner run not found",
            status_code=404,
        )
    decisions = await repository.list_decisions(run_id=run_id, limit=decision_limit)
    return AdminScannerRunDetailResponse(
        run=_run_to_response(run),
        decisions=[_decision_to_response(item) for item in decisions],
    )


@router.get("/live-decision", response_model=AdminLiveDecisionListResponse)
async def list_live_decisions(
    symbol: str | None = Query(None, description="Filter by symbol"),
    decision: str | None = Query(
        None,
        pattern="^(emitted|suppressed|skipped|error)$",
        description="Filter by scanner decision outcome",
    ),
    suppressed: bool | None = Query(None, description="Filter by suppression flag"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminLiveDecisionListResponse:
    repository = ScannerRunRepository(db)
    decisions = await repository.list_decisions(
        limit=limit,
        offset=offset,
        symbol=symbol,
        decision=decision,
        suppressed=suppressed,
    )
    total = await repository.count_decisions(
        symbol=symbol,
        decision=decision,
        suppressed=suppressed,
    )
    return AdminLiveDecisionListResponse(
        data=[_decision_to_response(item) for item in decisions],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(decisions)) < total,
    )
