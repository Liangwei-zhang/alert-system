from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from domains.signals.repository import SignalRepository
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/signal-stats", tags=["admin", "signal-stats"])


class AdminSignalStatsSymbolResponse(BaseModel):
    symbol: str
    count: int


class AdminSignalStatsSummaryResponse(BaseModel):
    window_hours: int
    generated_after: datetime
    total_signals: int
    pending_signals: int
    active_signals: int
    triggered_signals: int
    expired_signals: int
    cancelled_signals: int
    buy_signals: int
    sell_signals: int
    split_buy_signals: int
    split_sell_signals: int
    avg_probability: float
    avg_confidence: float
    top_symbols: list[AdminSignalStatsSymbolResponse]


class AdminSignalStatsItemResponse(BaseModel):
    id: int
    symbol: str
    signal_type: str
    status: str
    entry_price: float
    stop_loss: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    take_profit_3: float | None = None
    probability: float
    confidence: float
    risk_reward_ratio: float | None = None
    sfp_validated: bool
    chooch_validated: bool
    fvg_validated: bool
    validation_status: str
    atr_value: float | None = None
    atr_multiplier: float
    indicators: dict[str, Any] | list[Any] | None = None
    reasoning: str | None = None
    generated_at: datetime
    triggered_at: datetime | None = None
    expired_at: datetime | None = None


class AdminSignalStatsListResponse(BaseModel):
    data: list[AdminSignalStatsItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


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


def _signal_to_response(signal: Any) -> AdminSignalStatsItemResponse:
    return AdminSignalStatsItemResponse(
        id=int(signal.id),
        symbol=str(signal.symbol),
        signal_type=str(getattr(signal.signal_type, "value", signal.signal_type)),
        status=str(getattr(signal.status, "value", signal.status)),
        entry_price=float(signal.entry_price),
        stop_loss=(
            float(signal.stop_loss) if getattr(signal, "stop_loss", None) is not None else None
        ),
        take_profit_1=(
            float(signal.take_profit_1)
            if getattr(signal, "take_profit_1", None) is not None
            else None
        ),
        take_profit_2=(
            float(signal.take_profit_2)
            if getattr(signal, "take_profit_2", None) is not None
            else None
        ),
        take_profit_3=(
            float(signal.take_profit_3)
            if getattr(signal, "take_profit_3", None) is not None
            else None
        ),
        probability=float(signal.probability or 0.0),
        confidence=float(signal.confidence or 0.0),
        risk_reward_ratio=(
            float(signal.risk_reward_ratio)
            if getattr(signal, "risk_reward_ratio", None) is not None
            else None
        ),
        sfp_validated=bool(signal.sfp_validated),
        chooch_validated=bool(signal.chooch_validated),
        fvg_validated=bool(signal.fvg_validated),
        validation_status=str(getattr(signal.validation_status, "value", signal.validation_status)),
        atr_value=(
            float(signal.atr_value) if getattr(signal, "atr_value", None) is not None else None
        ),
        atr_multiplier=float(signal.atr_multiplier or 0.0),
        indicators=_load_payload(getattr(signal, "indicators", None)),
        reasoning=getattr(signal, "reasoning", None),
        generated_at=signal.generated_at,
        triggered_at=getattr(signal, "triggered_at", None),
        expired_at=getattr(signal, "expired_at", None),
    )


@router.get("/summary", response_model=AdminSignalStatsSummaryResponse)
async def get_signal_stats_summary(
    window_hours: int = Query(24 * 7, ge=1, le=24 * 365, description="Summary lookback window"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminSignalStatsSummaryResponse:
    summary = await SignalRepository(db).summarize_admin_signals(window_hours=window_hours)
    return AdminSignalStatsSummaryResponse(**summary)


@router.get("", response_model=AdminSignalStatsListResponse)
async def list_signal_stats(
    status: str | None = Query(
        None,
        pattern="^(pending|active|triggered|expired|cancelled)$",
        description="Filter by signal status",
    ),
    signal_type: str | None = Query(
        None,
        pattern="^(buy|sell|split_buy|split_sell)$",
        description="Filter by signal type",
    ),
    symbol: str | None = Query(None, description="Filter by symbol"),
    validation_status: str | None = Query(
        None,
        pattern="^(sfp|choch|fvg|validated)$",
        description="Filter by validation status",
    ),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminSignalStatsListResponse:
    repository = SignalRepository(db)
    signals = await repository.list_admin_signals(
        limit=limit,
        offset=offset,
        status=status,
        signal_type=signal_type,
        symbol=symbol,
        validation_status=validation_status,
    )
    total = await repository.count_admin_signals(
        status=status,
        signal_type=signal_type,
        symbol=symbol,
        validation_status=validation_status,
    )
    return AdminSignalStatsListResponse(
        data=[_signal_to_response(signal) for signal in signals],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(signals)) < total,
    )
