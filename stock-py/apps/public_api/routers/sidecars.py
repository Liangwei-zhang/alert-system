from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.market_data.proxy_service import MarketDataProxyService
from domains.notifications.bridge_alert_service import BridgeAlertService
from domains.notifications.telegram_relay_service import TelegramRelayService
from infra.core.config import get_settings
from infra.core.context import build_request_context
from infra.core.errors import AppError
from infra.db.session import get_db_session

router = APIRouter(tags=["sidecars"])

_ALLOWED_ALERT_CHANNELS = {"email", "push"}


class HistoricalBarResponse(BaseModel):
    date: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int


class MarketDataProxyResponse(BaseModel):
    source: str
    symbol: str
    period: str
    bars: list[HistoricalBarResponse]


class BridgeAlertRequest(BaseModel):
    user_ids: list[int] = Field(min_length=1, max_length=500)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=5000)
    channels: list[str] = Field(min_length=1, max_length=10)
    notification_type: str = Field(default="bridge.alert", min_length=1, max_length=50)
    ack_required: bool = False
    ack_deadline_at: datetime | None = None
    signal_id: str | None = None
    trade_id: str | None = None
    metadata: dict[str, Any] | None = None


class BridgeAlertResponse(BaseModel):
    message: str
    created_notifications: int
    requested_outbox: int
    resolved_user_ids: list[int]
    skipped_user_ids: list[int]
    notification_ids: list[str]
    outbox_ids: list[str]
    channels: list[str]


class TelegramRelayRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=5000)
    parse_mode: str | None = Field(default=None, max_length=20)
    disable_notification: bool = False


class TelegramRelayResponse(BaseModel):
    message: str
    ok: bool
    message_id: int
    chat_id: str


def _market_data_service() -> MarketDataProxyService:
    return MarketDataProxyService()


def _bridge_alert_service(session: AsyncSession) -> BridgeAlertService:
    return BridgeAlertService(session)


def _telegram_relay_service() -> TelegramRelayService:
    return TelegramRelayService()


def _resolve_request_context(request: Request):
    return getattr(request.state, "request_context", None) or build_request_context(request)


async def require_internal_sidecar_secret(
    x_internal_sidecar_secret: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    configured_secret = str(
        settings.internal_sidecar_secret or settings.internal_signal_ingest_secret or ""
    ).strip()
    if not configured_secret:
        if settings.debug:
            return
        raise AppError(
            "internal_sidecar_secret_missing",
            "Internal sidecar secret is not configured",
            status_code=503,
        )
    if x_internal_sidecar_secret != configured_secret:
        raise AppError(
            "internal_sidecar_forbidden",
            "Invalid internal sidecar secret",
            status_code=403,
        )


@router.get("/api/yahoo/{symbol}", response_model=MarketDataProxyResponse)
async def yahoo_proxy_history(
    symbol: str,
    period: str = Query(default="1mo"),
    _authorized: None = Depends(require_internal_sidecar_secret),
    service: MarketDataProxyService = Depends(_market_data_service),
) -> MarketDataProxyResponse:
    payload = await service.get_historical(source="yahoo", symbol=symbol, period=period)
    return MarketDataProxyResponse(**payload)


@router.get("/api/binance/{symbol}", response_model=MarketDataProxyResponse)
async def binance_proxy_history(
    symbol: str,
    period: str = Query(default="1mo"),
    _authorized: None = Depends(require_internal_sidecar_secret),
    service: MarketDataProxyService = Depends(_market_data_service),
) -> MarketDataProxyResponse:
    payload = await service.get_historical(source="binance", symbol=symbol, period=period)
    return MarketDataProxyResponse(**payload)


@router.post("/alerts", response_model=BridgeAlertResponse)
async def create_bridge_alert(
    request: BridgeAlertRequest,
    http_request: Request,
    _authorized: None = Depends(require_internal_sidecar_secret),
    session: AsyncSession = Depends(get_db_session),
) -> BridgeAlertResponse:
    channels = sorted(
        {str(channel).strip().lower() for channel in request.channels if str(channel).strip()}
    )
    if not channels:
        raise AppError(
            "bridge_alert_channels_empty",
            "At least one delivery channel is required",
            status_code=400,
        )
    invalid_channels = [channel for channel in channels if channel not in _ALLOWED_ALERT_CHANNELS]
    if invalid_channels:
        raise AppError(
            "bridge_alert_channel_invalid",
            f"Unsupported channels: {', '.join(invalid_channels)}",
            status_code=400,
        )

    service = _bridge_alert_service(session)
    result = await service.send_alert(
        context=_resolve_request_context(http_request),
        user_ids=request.user_ids,
        title=request.title,
        body=request.body,
        channels=channels,
        notification_type=request.notification_type,
        ack_required=request.ack_required,
        ack_deadline_at=request.ack_deadline_at,
        signal_id=request.signal_id,
        trade_id=request.trade_id,
        metadata=request.metadata,
    )
    return BridgeAlertResponse(
        message="Bridge alert queued",
        created_notifications=result.created_notifications,
        requested_outbox=result.requested_outbox,
        resolved_user_ids=result.resolved_user_ids,
        skipped_user_ids=result.skipped_user_ids,
        notification_ids=result.notification_ids,
        outbox_ids=result.outbox_ids,
        channels=channels,
    )


@router.post("/api/telegram", response_model=TelegramRelayResponse)
async def relay_telegram_message(
    request: TelegramRelayRequest,
    _authorized: None = Depends(require_internal_sidecar_secret),
    service: TelegramRelayService = Depends(_telegram_relay_service),
) -> TelegramRelayResponse:
    result = await service.send_message(
        chat_id=request.chat_id,
        text=request.text,
        parse_mode=request.parse_mode,
        disable_notification=request.disable_notification,
    )
    return TelegramRelayResponse(
        message="Telegram relay delivered",
        ok=bool(result["ok"]),
        message_id=int(result["message_id"]),
        chat_id=str(result["chat_id"]),
    )