from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.repository import SignalRepository
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(prefix="/signals", tags=["signals"])


class PublicStrategyBreakdownCandidateResponse(BaseModel):
    strategy: str
    source: str = "heuristic"
    source_strategy: str | None = None
    rank: int | None = None
    ranking_score: float | None = None
    combined_score: float | None = None
    signal_fit_score: float | None = None
    regime_bias: float | None = None
    degradation_penalty: float | None = None
    stable: bool = False
    market_regime_detail: str | None = None
    regime_duration_bars: int | None = None
    strategy_weight: float | None = None
    calibration_version: str | None = None


class PublicSignalStrategyBreakdownResponse(BaseModel):
    signal_id: int
    symbol: str
    signal_type: str
    strategy_window: str | None = None
    market_regime: str | None = None
    market_regime_detail: str | None = None
    regime_duration_bars: int | None = None
    regime_metrics: dict[str, float] = Field(default_factory=dict)
    regime_reasons: list[str] = Field(default_factory=list)
    calibration_version: str | None = None
    calibration_source: str | None = None
    calibration_effective_from: datetime | None = None
    selected_strategy: str | None = None
    selection_source: str | None = None
    source_strategy: str | None = None
    selected_candidate: PublicStrategyBreakdownCandidateResponse | None = None
    candidates: list[PublicStrategyBreakdownCandidateResponse] = Field(default_factory=list)
    alert_decision: dict[str, Any] | None = None
    generated_at: datetime


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _candidate_payload(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "strategy": str(item.get("strategy") or "unknown"),
        "source": str(item.get("source") or "heuristic"),
        "source_strategy": str(item.get("source_strategy") or item.get("strategy") or "unknown"),
        "rank": int(item.get("rank")) if item.get("rank") not in (None, "") else None,
        "ranking_score": float(item.get("ranking_score")) if item.get("ranking_score") not in (None, "") else None,
        "combined_score": float(item.get("combined_score")) if item.get("combined_score") not in (None, "") else None,
        "signal_fit_score": float(item.get("signal_fit_score")) if item.get("signal_fit_score") not in (None, "") else None,
        "regime_bias": float(item.get("regime_bias")) if item.get("regime_bias") not in (None, "") else None,
        "degradation_penalty": float(item.get("degradation_penalty")) if item.get("degradation_penalty") not in (None, "") else None,
        "stable": bool(item.get("stable", False)),
        "market_regime_detail": str(item.get("market_regime_detail")).strip() if item.get("market_regime_detail") else None,
        "regime_duration_bars": int(item.get("regime_duration_bars")) if item.get("regime_duration_bars") not in (None, "") else None,
        "strategy_weight": float(item.get("strategy_weight")) if item.get("strategy_weight") not in (None, "") else None,
        "calibration_version": str(item.get("calibration_version")).strip() if item.get("calibration_version") else None,
    }


@router.get("/{signal_id}/strategy-breakdown", response_model=PublicSignalStrategyBreakdownResponse)
async def get_signal_strategy_breakdown(
    signal_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> PublicSignalStrategyBreakdownResponse:
    signal = await SignalRepository(db).get_signal(signal_id)
    if signal is None:
        raise AppError(
            code="signal_not_found",
            message="Signal not found",
            status_code=404,
        )

    metadata = SignalRepository._load_metadata(signal)
    strategy_selection = _as_dict(metadata.get("strategy_selection"))
    calibration_snapshot = _as_dict(metadata.get("calibration_snapshot"))
    candidates = _as_list_of_dicts(metadata.get("strategy_candidates"))
    if strategy_selection and not candidates:
        candidates = [strategy_selection]

    selected_candidate = _candidate_payload(strategy_selection) if strategy_selection else None
    return PublicSignalStrategyBreakdownResponse(
        signal_id=int(signal.id),
        symbol=str(signal.symbol),
        signal_type=str(getattr(signal.signal_type, "value", signal.signal_type)),
        strategy_window=str(metadata.get("strategy_window")).strip() if metadata.get("strategy_window") else None,
        market_regime=str(metadata.get("market_regime")).strip() if metadata.get("market_regime") else None,
        market_regime_detail=str(metadata.get("market_regime_detail")).strip() if metadata.get("market_regime_detail") else None,
        regime_duration_bars=int(metadata.get("regime_duration_bars")) if metadata.get("regime_duration_bars") not in (None, "") else None,
        regime_metrics={
            str(key): float(value)
            for key, value in _as_dict(metadata.get("regime_metrics")).items()
            if value not in (None, "")
        },
        regime_reasons=[str(item).strip() for item in list(metadata.get("regime_reasons") or []) if str(item).strip()],
        calibration_version=(
            str(metadata.get("calibration_version") or strategy_selection.get("calibration_version") or calibration_snapshot.get("version") or "").strip()
            or None
        ),
        calibration_source=str(calibration_snapshot.get("source")).strip() if calibration_snapshot.get("source") else None,
        calibration_effective_from=_parse_datetime(
            calibration_snapshot.get("effective_from") or calibration_snapshot.get("effective_at")
        ),
        selected_strategy=str(strategy_selection.get("strategy")).strip() if strategy_selection.get("strategy") else None,
        selection_source=str(strategy_selection.get("source")).strip() if strategy_selection.get("source") else None,
        source_strategy=str(strategy_selection.get("source_strategy")).strip() if strategy_selection.get("source_strategy") else None,
        selected_candidate=(
            PublicStrategyBreakdownCandidateResponse(**selected_candidate)
            if selected_candidate is not None
            else None
        ),
        candidates=[PublicStrategyBreakdownCandidateResponse(**_candidate_payload(item)) for item in candidates],
        alert_decision=_as_dict(metadata.get("alert_decision")) or None,
        generated_at=signal.generated_at,
    )