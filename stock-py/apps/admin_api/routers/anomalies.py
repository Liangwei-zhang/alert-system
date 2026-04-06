from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.repository import OhlcvRepository
from infra.db.session import get_db_session

router = APIRouter(prefix="/v1/admin/anomalies", tags=["admin", "anomalies"])


class AdminOhlcvAnomalyResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    bar_time: datetime | None = None
    anomaly_code: str
    severity: str
    details: dict[str, Any] | list[Any] | None = None
    source: str | None = None
    quarantined_at: datetime


class AdminOhlcvAnomalyListResponse(BaseModel):
    data: list[AdminOhlcvAnomalyResponse]
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


def _anomaly_to_response(anomaly: Any) -> AdminOhlcvAnomalyResponse:
    return AdminOhlcvAnomalyResponse(
        id=int(anomaly.id),
        symbol=str(anomaly.symbol),
        timeframe=str(anomaly.timeframe),
        bar_time=getattr(anomaly, "bar_time", None),
        anomaly_code=str(anomaly.anomaly_code),
        severity=str(anomaly.severity),
        details=_load_payload(getattr(anomaly, "details", None)),
        source=str(anomaly.source) if getattr(anomaly, "source", None) else None,
        quarantined_at=anomaly.quarantined_at,
    )


@router.get("/ohlcv", response_model=AdminOhlcvAnomalyListResponse)
async def list_ohlcv_anomalies(
    symbol: str | None = Query(None, description="Filter by symbol"),
    timeframe: str | None = Query(None, description="Filter by timeframe"),
    severity: str | None = Query(
        None,
        pattern="^(warning|error|critical)$",
        description="Filter by anomaly severity",
    ),
    anomaly_code: str | None = Query(None, description="Filter by anomaly code"),
    source: str | None = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOhlcvAnomalyListResponse:
    repository = OhlcvRepository(db)
    anomalies = await repository.list_anomalies(
        limit=limit,
        offset=offset,
        symbol=symbol,
        timeframe=timeframe,
        severity=severity,
        anomaly_code=anomaly_code,
        source=source,
    )
    total = await repository.count_anomalies(
        symbol=symbol,
        timeframe=timeframe,
        severity=severity,
        anomaly_code=anomaly_code,
        source=source,
    )
    return AdminOhlcvAnomalyListResponse(
        data=[_anomaly_to_response(item) for item in anomalies],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(anomalies)) < total,
    )
