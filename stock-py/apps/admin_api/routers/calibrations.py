from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.admin_api.dependencies import get_analytics_repository
from domains.analytics.repository import AnalyticsRepository
from domains.signals.calibration_proposal_service import CalibrationProposalService
from domains.signals.calibration_repository import SignalCalibrationSnapshotRepository
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/calibrations", tags=["admin", "calibrations"])


class AdminCalibrationSnapshotItemResponse(BaseModel):
    id: int
    version: str
    source: str
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    score_multipliers: dict[str, float] = Field(default_factory=dict)
    derived_from: str | None = None
    sample_size: int | None = None
    is_active: bool
    effective_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class AdminCalibrationSnapshotListResponse(BaseModel):
    data: list[AdminCalibrationSnapshotItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AdminActiveCalibrationSnapshotResponse(BaseModel):
    data: AdminCalibrationSnapshotItemResponse | None = None


class CreateCalibrationSnapshotRequest(BaseModel):
    version: str = Field(min_length=1, max_length=120)
    source: str = Field(default="manual_review", min_length=1, max_length=48)
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    score_multipliers: dict[str, float] = Field(default_factory=dict)
    derived_from: str | None = Field(default=None, max_length=160)
    sample_size: int | None = Field(default=None, ge=0)
    activate: bool = False
    effective_at: datetime | None = None
    notes: str | None = None


class AdminCalibrationProposalAdjustmentResponse(BaseModel):
    key: str
    current_value: float
    proposed_value: float
    delta: float
    reasons: list[str] = Field(default_factory=list)


class AdminCalibrationProposalSummaryResponse(BaseModel):
    total_signals: int
    total_trade_actions: int
    trade_action_rate: float
    executed_trade_rate: float
    overlapping_symbols: int
    active_calibration_version: str


class AdminCalibrationProposalSnapshotPayloadResponse(BaseModel):
    version: str
    source: str
    strategy_weights: dict[str, float] = Field(default_factory=dict)
    score_multipliers: dict[str, float] = Field(default_factory=dict)
    derived_from: str | None = None
    sample_size: int | None = None
    notes: str | None = None


class AdminCalibrationProposalResponse(BaseModel):
    generated_at: datetime
    signal_window_hours: int
    ranking_window_hours: int
    current_version: str
    proposed_version: str
    strategy_health_refreshed_at: datetime | None = None
    signal_generated_after: datetime | None = None
    summary: AdminCalibrationProposalSummaryResponse
    strategy_weights: list[AdminCalibrationProposalAdjustmentResponse] = Field(default_factory=list)
    score_multipliers: list[AdminCalibrationProposalAdjustmentResponse] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    snapshot_payload: AdminCalibrationProposalSnapshotPayloadResponse


class ApplyCalibrationProposalRequest(BaseModel):
    signal_window_hours: int = Field(default=24, ge=1, le=24 * 30)
    ranking_window_hours: int = Field(default=24 * 7, ge=1, le=24 * 90)
    version: str | None = Field(default=None, min_length=1, max_length=120)
    activate: bool = False
    notes: str | None = None


@router.get("", response_model=AdminCalibrationSnapshotListResponse)
async def list_calibration_snapshots(
    active_only: bool = Query(False, description="Return active snapshots only"),
    limit: int = Query(20, ge=1, le=100, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminCalibrationSnapshotListResponse:
    repository = SignalCalibrationSnapshotRepository(db)
    items = await repository.list_snapshots(limit=limit, offset=offset, active_only=active_only)
    total = await repository.count_snapshots(active_only=active_only)
    return AdminCalibrationSnapshotListResponse(
        data=[AdminCalibrationSnapshotItemResponse(**item) for item in items],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/active", response_model=AdminActiveCalibrationSnapshotResponse)
async def get_active_calibration_snapshot(
    db: AsyncSession = Depends(get_db_session),
) -> AdminActiveCalibrationSnapshotResponse:
    snapshot = await SignalCalibrationSnapshotRepository(db).get_active_snapshot()
    if snapshot is None:
        return AdminActiveCalibrationSnapshotResponse(data=None)
    return AdminActiveCalibrationSnapshotResponse(
        data=AdminCalibrationSnapshotItemResponse(**snapshot)
    )


@router.get("/proposal", response_model=AdminCalibrationProposalResponse)
async def get_calibration_proposal(
    signal_window_hours: int = Query(24, ge=1, le=24 * 30),
    ranking_window_hours: int = Query(24 * 7, ge=1, le=24 * 90),
    db: AsyncSession = Depends(get_db_session),
    analytics_repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> AdminCalibrationProposalResponse:
    proposal = await CalibrationProposalService(
        analytics_repository=analytics_repository,
        calibration_repository=SignalCalibrationSnapshotRepository(db),
    ).build_proposal(
        signal_window_hours=signal_window_hours,
        ranking_window_hours=ranking_window_hours,
    )
    return AdminCalibrationProposalResponse(**proposal)


@router.post("/{snapshot_id}/activate", response_model=AdminCalibrationSnapshotItemResponse)
async def activate_calibration_snapshot(
    snapshot_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> AdminCalibrationSnapshotItemResponse:
    repository = SignalCalibrationSnapshotRepository(db)
    try:
        snapshot = await repository.activate_snapshot(snapshot_id)
    except ValueError as exc:
        raise AppError(
            code="calibration_snapshot_not_found",
            message=str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    return AdminCalibrationSnapshotItemResponse(**snapshot)


@router.post("/proposal/apply", response_model=AdminCalibrationSnapshotItemResponse)
async def apply_calibration_proposal(
    request: ApplyCalibrationProposalRequest,
    db: AsyncSession = Depends(get_db_session),
    analytics_repository: AnalyticsRepository = Depends(get_analytics_repository),
) -> AdminCalibrationSnapshotItemResponse:
    repository = SignalCalibrationSnapshotRepository(db)
    proposal = await CalibrationProposalService(
        analytics_repository=analytics_repository,
        calibration_repository=repository,
    ).build_proposal(
        signal_window_hours=request.signal_window_hours,
        ranking_window_hours=request.ranking_window_hours,
    )
    snapshot_payload = dict(proposal["snapshot_payload"])
    notes_parts = [snapshot_payload.get("notes"), request.notes]
    notes = "; ".join(part for part in notes_parts if isinstance(part, str) and part.strip()) or None

    try:
        snapshot = await repository.create_snapshot(
            version=str(request.version or snapshot_payload.get("version") or "").strip(),
            source="proposal_review",
            strategy_weights=dict(snapshot_payload.get("strategy_weights") or {}),
            score_multipliers=dict(snapshot_payload.get("score_multipliers") or {}),
            derived_from=snapshot_payload.get("derived_from"),
            sample_size=snapshot_payload.get("sample_size"),
            activate=request.activate,
            notes=notes,
        )
    except ValueError as exc:
        raise AppError(
            code="calibration_snapshot_conflict",
            message=str(exc),
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return AdminCalibrationSnapshotItemResponse(**snapshot)


@router.post(
    "",
    response_model=AdminCalibrationSnapshotItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_calibration_snapshot(
    payload: CreateCalibrationSnapshotRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AdminCalibrationSnapshotItemResponse:
    repository = SignalCalibrationSnapshotRepository(db)
    try:
        snapshot = await repository.create_snapshot(
            version=payload.version,
            source=payload.source,
            strategy_weights=payload.strategy_weights,
            score_multipliers=payload.score_multipliers,
            derived_from=payload.derived_from,
            sample_size=payload.sample_size,
            activate=payload.activate,
            effective_at=payload.effective_at,
            notes=payload.notes,
        )
    except ValueError as exc:
        raise AppError(
            code="calibration_snapshot_conflict",
            message=str(exc),
            status_code=status.HTTP_409_CONFLICT,
        ) from exc
    return AdminCalibrationSnapshotItemResponse(**snapshot)