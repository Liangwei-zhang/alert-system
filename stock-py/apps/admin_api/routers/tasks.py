from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.admin.repository import OperatorRepository
from domains.notifications.receipt_service import ReceiptEscalationService
from domains.notifications.repository import MessageOutboxRepository, ReceiptRepository
from domains.trades.repository import TradeRepository
from infra.core.context import build_request_context
from infra.core.errors import AppError
from infra.db.session import get_db_session
from infra.events.outbox import OutboxPublisher

router = APIRouter(prefix="/v1/admin/tasks", tags=["admin", "tasks"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _resolve_request_context(request: Request):
    return getattr(request.state, "request_context", None) or build_request_context(request)


async def _require_active_operator_id(request: Request, db: AsyncSession) -> tuple[int, object]:
    context = _resolve_request_context(request)
    raw_operator_id = context.operator_id
    if raw_operator_id is None:
        raise AppError(
            code="admin_operator_required",
            message="X-Operator-ID header is required",
            status_code=400,
        )
    try:
        operator_user_id = int(str(raw_operator_id))
    except ValueError as exc:
        raise AppError(
            code="admin_operator_invalid",
            message="X-Operator-ID must be an integer",
            status_code=400,
        ) from exc
    operator, _user = await OperatorRepository(db).get_active_operator(
        operator_user_id,
        allowed_roles={"operator", "admin"},
    )
    if operator is None:
        raise AppError(
            code="admin_operator_forbidden",
            message="Active operator access is required",
            status_code=403,
        )
    return operator_user_id, context


class AdminReceiptItemResponse(BaseModel):
    id: str
    notification_id: str
    user_id: int
    ack_required: bool
    ack_deadline_at: datetime | None = None
    opened_at: datetime | None = None
    acknowledged_at: datetime | None = None
    last_delivery_channel: str | None = None
    last_delivery_status: str | None = None
    escalation_level: int = 0
    manual_follow_up_status: str
    manual_follow_up_updated_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    overdue: bool = False


class AdminReceiptListResponse(BaseModel):
    data: list[AdminReceiptItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class AdminOutboxItemResponse(BaseModel):
    id: str
    notification_id: str | None = None
    user_id: int
    channel: str
    status: str
    payload: dict = Field(default_factory=dict)
    last_error: str | None = None
    created_at: datetime


class AdminOutboxListResponse(BaseModel):
    data: list[AdminOutboxItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ReceiptEscalationRunResponse(BaseModel):
    scanned: int
    escalated: int
    skipped: int


class ReceiptFollowUpActionResponse(BaseModel):
    message: str
    receipt: AdminReceiptItemResponse


class ReceiptAckRequest(BaseModel):
    receipt_id: str


class OutboxActionResponse(BaseModel):
    message: str
    outbox: AdminOutboxItemResponse


class BulkOutboxActionRequest(BaseModel):
    outbox_ids: list[str] = Field(min_length=1, max_length=500)


class BulkOutboxActionResponse(BaseModel):
    message: str
    processed_count: int
    outbox: list[AdminOutboxItemResponse]
    skipped_outbox_ids: list[str] = Field(default_factory=list)


class AdminTradeTaskItemResponse(BaseModel):
    id: str
    user_id: int
    symbol: str
    action: str
    status: str
    suggested_shares: float
    suggested_price: float
    suggested_amount: float
    actual_shares: float | None = None
    actual_price: float | None = None
    actual_amount: float | None = None
    expires_at: datetime
    claimed_by_operator_id: int | None = None
    claimed_at: datetime | None = None
    confirmed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    is_expired: bool = False


class AdminTradeTaskListResponse(BaseModel):
    data: list[AdminTradeTaskItemResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class ExpireTradesRequest(BaseModel):
    trade_ids: list[str] | None = None
    limit: int = Field(100, ge=1, le=1000)
    user_id: int | None = Field(None, ge=1)
    symbol: str | None = None


class ClaimTradesRequest(BaseModel):
    trade_ids: list[str] | None = None
    limit: int = Field(100, ge=1, le=1000)
    user_id: int | None = Field(None, ge=1)
    symbol: str | None = None


class BulkTradeActionResponse(BaseModel):
    message: str
    processed_count: int
    trades: list[AdminTradeTaskItemResponse]
    skipped_trade_ids: list[str] = Field(default_factory=list)


def _is_receipt_overdue(receipt) -> bool:
    ack_deadline_at = getattr(receipt, "ack_deadline_at", None)
    if ack_deadline_at is None:
        return False
    if getattr(receipt, "ack_required", False) is not True:
        return False
    if getattr(receipt, "acknowledged_at", None) is not None:
        return False
    return ack_deadline_at < utcnow()


def _receipt_to_response(receipt) -> AdminReceiptItemResponse:
    return AdminReceiptItemResponse(
        id=str(receipt.id),
        notification_id=str(receipt.notification_id),
        user_id=int(receipt.user_id),
        ack_required=bool(receipt.ack_required),
        ack_deadline_at=receipt.ack_deadline_at,
        opened_at=receipt.opened_at,
        acknowledged_at=receipt.acknowledged_at,
        last_delivery_channel=receipt.last_delivery_channel,
        last_delivery_status=receipt.last_delivery_status,
        escalation_level=int(receipt.escalation_level or 0),
        manual_follow_up_status=str(receipt.manual_follow_up_status or "none"),
        manual_follow_up_updated_at=receipt.manual_follow_up_updated_at,
        created_at=receipt.created_at,
        updated_at=receipt.updated_at,
        overdue=_is_receipt_overdue(receipt),
    )


def _outbox_to_response(message) -> AdminOutboxItemResponse:
    payload = dict(getattr(message, "payload", {}) or {})
    last_error = payload.get("_last_error")
    return AdminOutboxItemResponse(
        id=str(message.id),
        notification_id=(
            str(message.notification_id) if getattr(message, "notification_id", None) else None
        ),
        user_id=int(message.user_id),
        channel=str(message.channel),
        status=str(message.status),
        payload=payload,
        last_error=str(last_error) if last_error else None,
        created_at=message.created_at,
    )


def _is_trade_expired(trade) -> bool:
    status = str(getattr(trade, "status", "")).lower()
    if status == "expired":
        return True
    expires_at = getattr(trade, "expires_at", None)
    if expires_at is None:
        return False
    return expires_at < utcnow()


def _trade_to_response(trade) -> AdminTradeTaskItemResponse:
    action = getattr(trade, "action", None)
    status = getattr(trade, "status", None)
    return AdminTradeTaskItemResponse(
        id=str(trade.id),
        user_id=int(trade.user_id),
        symbol=str(trade.symbol),
        action=str(getattr(action, "value", action)),
        status=str(getattr(status, "value", status)),
        suggested_shares=float(trade.suggested_shares),
        suggested_price=float(trade.suggested_price),
        suggested_amount=float(trade.suggested_amount),
        actual_shares=(
            float(trade.actual_shares)
            if getattr(trade, "actual_shares", None) is not None
            else None
        ),
        actual_price=(
            float(trade.actual_price) if getattr(trade, "actual_price", None) is not None else None
        ),
        actual_amount=(
            float(trade.actual_amount)
            if getattr(trade, "actual_amount", None) is not None
            else None
        ),
        expires_at=trade.expires_at,
        claimed_by_operator_id=getattr(trade, "claimed_by_operator_id", None),
        claimed_at=getattr(trade, "claimed_at", None),
        confirmed_at=getattr(trade, "confirmed_at", None),
        created_at=trade.created_at,
        updated_at=trade.updated_at,
        is_expired=_is_trade_expired(trade),
    )


async def _requeue_outbox_messages(
    repository: MessageOutboxRepository,
    outbox_ids: list[str],
    *,
    channel: str | None = None,
) -> tuple[list, list[str]]:
    seen: set[str] = set()
    requeued_messages: list = []
    skipped_outbox_ids: list[str] = []
    for raw_outbox_id in outbox_ids:
        outbox_id = str(raw_outbox_id)
        if not outbox_id or outbox_id in seen:
            continue
        seen.add(outbox_id)

        message = await repository.get_by_id(outbox_id)
        if message is None:
            skipped_outbox_ids.append(outbox_id)
            continue
        if channel is not None and str(message.channel) != channel:
            skipped_outbox_ids.append(outbox_id)
            continue
        if str(message.status) == "delivered":
            skipped_outbox_ids.append(outbox_id)
            continue

        requeued = await repository.requeue(outbox_id)
        if requeued is None:
            skipped_outbox_ids.append(outbox_id)
            continue
        requeued_messages.append(requeued)

    return requeued_messages, skipped_outbox_ids


@router.get("", response_model=dict)
async def get_tasks_root() -> dict[str, object]:
    return {
        "areas": ["receipts", "outbox", "emails", "trades"],
        "actions": [
            "receipts:list",
            "receipts:ack",
            "receipts:escalate-overdue",
            "receipts:claim",
            "receipts:resolve",
            "emails:claim",
            "emails:retry",
            "outbox:list",
            "outbox:requeue",
            "outbox:retry",
            "outbox:release-stale",
            "trades:list",
            "trades:claim",
            "trades:expire",
        ],
    }


@router.get("/receipts", response_model=AdminReceiptListResponse)
async def list_receipts(
    follow_up_status: str | None = Query(
        None,
        pattern="^(none|pending|claimed|resolved)$",
        description="Filter by manual follow-up status",
    ),
    delivery_status: str | None = Query(
        None,
        pattern="^(pending|delivered|failed)$",
        description="Filter by last delivery status",
    ),
    ack_required: bool | None = Query(None, description="Filter by acknowledgement requirement"),
    overdue_only: bool = Query(False, description="Only include overdue acknowledgements"),
    user_id: int | None = Query(None, ge=1, description="Filter by user id"),
    notification_id: str | None = Query(None, description="Filter by notification id"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminReceiptListResponse:
    repository = ReceiptRepository(db)
    receipts = await repository.list_admin_receipts(
        limit=limit,
        offset=offset,
        follow_up_status=follow_up_status,
        delivery_status=delivery_status,
        ack_required=ack_required,
        overdue_only=overdue_only,
        user_id=user_id,
        notification_id=notification_id,
    )
    total = await repository.count_admin_receipts(
        follow_up_status=follow_up_status,
        delivery_status=delivery_status,
        ack_required=ack_required,
        overdue_only=overdue_only,
        user_id=user_id,
        notification_id=notification_id,
    )
    return AdminReceiptListResponse(
        data=[_receipt_to_response(receipt) for receipt in receipts],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(receipts)) < total,
    )


@router.post("/receipts/escalate-overdue", response_model=ReceiptEscalationRunResponse)
async def escalate_overdue_receipts(
    limit: int = Query(100, ge=1, le=1000, description="Maximum overdue receipts to scan"),
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptEscalationRunResponse:
    service = ReceiptEscalationService(ReceiptRepository(db))
    summary = await service.scan_and_escalate(limit=limit)
    return ReceiptEscalationRunResponse(
        scanned=summary.scanned,
        escalated=summary.escalated,
        skipped=summary.skipped,
    )


@router.post("/receipts/ack", response_model=ReceiptFollowUpActionResponse)
async def acknowledge_receipt(
    request: ReceiptAckRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptFollowUpActionResponse:
    repository = ReceiptRepository(db)
    receipt = await repository.get_by_id(request.receipt_id)
    if receipt is None:
        raise AppError("receipt_not_found", "Receipt not found", status_code=404)
    acknowledged = await repository.acknowledge(str(receipt.notification_id), int(receipt.user_id))
    if acknowledged is None:
        raise AppError("receipt_not_found", "Receipt not found", status_code=404)
    return ReceiptFollowUpActionResponse(
        message="Receipt acknowledged",
        receipt=_receipt_to_response(acknowledged),
    )


@router.post("/receipts/{receipt_id}/claim", response_model=ReceiptFollowUpActionResponse)
async def claim_receipt_follow_up(
    receipt_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptFollowUpActionResponse:
    service = ReceiptEscalationService(ReceiptRepository(db))
    receipt = await service.claim_manual_follow_up(receipt_id)
    return ReceiptFollowUpActionResponse(
        message="Receipt follow-up claimed",
        receipt=_receipt_to_response(receipt),
    )


@router.post("/receipts/{receipt_id}/resolve", response_model=ReceiptFollowUpActionResponse)
async def resolve_receipt_follow_up(
    receipt_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> ReceiptFollowUpActionResponse:
    service = ReceiptEscalationService(ReceiptRepository(db))
    receipt = await service.resolve_follow_up(receipt_id)
    return ReceiptFollowUpActionResponse(
        message="Receipt follow-up resolved",
        receipt=_receipt_to_response(receipt),
    )


@router.post("/emails/claim", response_model=BulkOutboxActionResponse)
async def claim_email_tasks(
    limit: int = Query(100, ge=1, le=1000, description="Maximum email tasks to claim"),
    db: AsyncSession = Depends(get_db_session),
) -> BulkOutboxActionResponse:
    repository = MessageOutboxRepository(db)
    messages = await repository.claim_pending("email", limit=limit)
    return BulkOutboxActionResponse(
        message="Email tasks claimed",
        processed_count=len(messages),
        outbox=[_outbox_to_response(message) for message in messages],
        skipped_outbox_ids=[],
    )


@router.post("/emails/retry", response_model=BulkOutboxActionResponse)
async def retry_email_tasks(
    request: BulkOutboxActionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkOutboxActionResponse:
    repository = MessageOutboxRepository(db)
    requeued_messages, skipped_outbox_ids = await _requeue_outbox_messages(
        repository,
        request.outbox_ids,
        channel="email",
    )
    return BulkOutboxActionResponse(
        message="Email tasks requeued",
        processed_count=len(requeued_messages),
        outbox=[_outbox_to_response(message) for message in requeued_messages],
        skipped_outbox_ids=skipped_outbox_ids,
    )


@router.get("/trades", response_model=AdminTradeTaskListResponse)
async def list_trade_tasks(
    status: str | None = Query(
        None,
        pattern="^(pending|confirmed|adjusted|ignored|expired)$",
        description="Filter by trade status",
    ),
    action: str | None = Query(
        None,
        pattern="^(buy|sell|add)$",
        description="Filter by trade action",
    ),
    expired_only: bool = Query(False, description="Only include expired or expirable trades"),
    claimed_only: bool = Query(False, description="Only include claimed trades"),
    claimed_by_operator_id: int | None = Query(
        None,
        ge=1,
        description="Filter by claiming operator user id",
    ),
    user_id: int | None = Query(None, ge=1, description="Filter by user id"),
    symbol: str | None = Query(None, description="Filter by symbol"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminTradeTaskListResponse:
    repository = TradeRepository(db)
    trades = await repository.list_admin_trades(
        limit=limit,
        offset=offset,
        status=status,
        action=action,
        user_id=user_id,
        symbol=symbol,
        expired_only=expired_only,
        claimed_only=claimed_only,
        claimed_by_operator_id=claimed_by_operator_id,
    )
    total = await repository.count_admin_trades(
        status=status,
        action=action,
        user_id=user_id,
        symbol=symbol,
        expired_only=expired_only,
        claimed_only=claimed_only,
        claimed_by_operator_id=claimed_by_operator_id,
    )
    return AdminTradeTaskListResponse(
        data=[_trade_to_response(trade) for trade in trades],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(trades)) < total,
    )


@router.post("/trades/claim", response_model=BulkTradeActionResponse)
async def claim_trade_tasks(
    request: ClaimTradesRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> BulkTradeActionResponse:
    operator_user_id, context = await _require_active_operator_id(http_request, db)
    repository = TradeRepository(db)
    claimed_trades: list = []
    skipped_trade_ids: list[str] = []

    if request.trade_ids:
        seen: set[str] = set()
        normalized_symbol = request.symbol.strip().upper() if request.symbol else None
        for raw_trade_id in request.trade_ids:
            trade_id = str(raw_trade_id)
            if not trade_id or trade_id in seen:
                continue
            seen.add(trade_id)

            trade = await repository.get_by_id(trade_id)
            if trade is None:
                skipped_trade_ids.append(trade_id)
                continue
            if request.user_id is not None and int(trade.user_id) != request.user_id:
                skipped_trade_ids.append(trade_id)
                continue
            if normalized_symbol is not None and str(trade.symbol) != normalized_symbol:
                skipped_trade_ids.append(trade_id)
                continue
            claimed = await repository.claim(trade_id, operator_user_id)
            if claimed is None:
                skipped_trade_ids.append(trade_id)
                continue
            claimed_trades.append(claimed)
    else:
        candidates = await repository.list_claimable_trades(
            limit=request.limit,
            user_id=request.user_id,
            symbol=request.symbol,
        )
        for trade in candidates:
            claimed = await repository.claim(str(trade.id), operator_user_id)
            if claimed is None:
                skipped_trade_ids.append(str(trade.id))
                continue
            claimed_trades.append(claimed)

    await OperatorRepository(db).touch_operator(operator_user_id)
    await OutboxPublisher(db).publish_after_commit(
        topic="ops.audit.logged",
        key=f"trade-claim:{context.request_id}",
        payload={
            "entity": "trade",
            "entity_id": context.request_id,
            "action": "tasks.claimed",
            "source": "admin-api",
            "operator_id": operator_user_id,
            "trade_ids": [str(trade.id) for trade in claimed_trades],
            "skipped_trade_ids": skipped_trade_ids,
            "processed_count": len(claimed_trades),
            "request_id": context.request_id,
        },
        headers={
            "request_id": context.request_id,
            "operator_id": str(operator_user_id),
        },
    )
    return BulkTradeActionResponse(
        message="Trades claimed",
        processed_count=len(claimed_trades),
        trades=[_trade_to_response(trade) for trade in claimed_trades],
        skipped_trade_ids=skipped_trade_ids,
    )


@router.post("/trades/expire", response_model=BulkTradeActionResponse)
async def expire_trade_tasks(
    request: ExpireTradesRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkTradeActionResponse:
    repository = TradeRepository(db)
    expired_trades: list = []
    skipped_trade_ids: list[str] = []

    if request.trade_ids:
        seen: set[str] = set()
        normalized_symbol = request.symbol.strip().upper() if request.symbol else None
        for raw_trade_id in request.trade_ids:
            trade_id = str(raw_trade_id)
            if not trade_id or trade_id in seen:
                continue
            seen.add(trade_id)

            trade = await repository.get_by_id(trade_id)
            if trade is None:
                skipped_trade_ids.append(trade_id)
                continue
            if request.user_id is not None and int(trade.user_id) != request.user_id:
                skipped_trade_ids.append(trade_id)
                continue
            if normalized_symbol is not None and str(trade.symbol) != normalized_symbol:
                skipped_trade_ids.append(trade_id)
                continue
            expired = await repository.mark_expired(trade_id)
            if expired is None:
                skipped_trade_ids.append(trade_id)
                continue
            expired_trades.append(expired)
    else:
        candidates = await repository.list_expirable_trades(
            limit=request.limit,
            user_id=request.user_id,
            symbol=request.symbol,
        )
        for trade in candidates:
            expired = await repository.mark_expired(str(trade.id))
            if expired is None:
                skipped_trade_ids.append(str(trade.id))
                continue
            expired_trades.append(expired)

    return BulkTradeActionResponse(
        message="Trades expired",
        processed_count=len(expired_trades),
        trades=[_trade_to_response(trade) for trade in expired_trades],
        skipped_trade_ids=skipped_trade_ids,
    )


@router.get("/outbox", response_model=AdminOutboxListResponse)
async def list_outbox(
    channel: str | None = Query(
        None,
        pattern="^(push|email)$",
        description="Filter by delivery channel",
    ),
    status: str | None = Query(
        None,
        pattern="^(pending|processing|delivered|failed)$",
        description="Filter by outbox status",
    ),
    user_id: int | None = Query(None, ge=1, description="Filter by user id"),
    notification_id: str | None = Query(None, description="Filter by notification id"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminOutboxListResponse:
    repository = MessageOutboxRepository(db)
    messages = await repository.list_admin_messages(
        limit=limit,
        offset=offset,
        channel=channel,
        status=status,
        user_id=user_id,
        notification_id=notification_id,
    )
    total = await repository.count_admin_messages(
        channel=channel,
        status=status,
        user_id=user_id,
        notification_id=notification_id,
    )
    return AdminOutboxListResponse(
        data=[_outbox_to_response(message) for message in messages],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(messages)) < total,
    )


@router.post("/outbox/retry", response_model=BulkOutboxActionResponse)
async def retry_outbox_messages(
    request: BulkOutboxActionRequest,
    db: AsyncSession = Depends(get_db_session),
) -> BulkOutboxActionResponse:
    repository = MessageOutboxRepository(db)
    requeued_messages, skipped_outbox_ids = await _requeue_outbox_messages(
        repository,
        request.outbox_ids,
    )
    return BulkOutboxActionResponse(
        message="Outbox messages requeued",
        processed_count=len(requeued_messages),
        outbox=[_outbox_to_response(message) for message in requeued_messages],
        skipped_outbox_ids=skipped_outbox_ids,
    )


@router.post("/outbox/release-stale", response_model=BulkOutboxActionResponse)
async def release_stale_outbox_messages(
    channel: str | None = Query(
        None,
        pattern="^(push|email)$",
        description="Filter by delivery channel",
    ),
    older_than_minutes: int = Query(
        15,
        ge=1,
        le=1440,
        description="Release processing tasks older than this many minutes",
    ),
    limit: int = Query(100, ge=1, le=1000, description="Maximum stale tasks to release"),
    db: AsyncSession = Depends(get_db_session),
) -> BulkOutboxActionResponse:
    repository = MessageOutboxRepository(db)
    released_messages = await repository.release_stale_processing(
        channel=channel,
        older_than_minutes=older_than_minutes,
        limit=limit,
    )
    return BulkOutboxActionResponse(
        message="Stale outbox messages released",
        processed_count=len(released_messages),
        outbox=[_outbox_to_response(message) for message in released_messages],
        skipped_outbox_ids=[],
    )


@router.post("/outbox/{outbox_id}/requeue", response_model=OutboxActionResponse)
async def requeue_outbox_message(
    outbox_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> OutboxActionResponse:
    repository = MessageOutboxRepository(db)
    message = await repository.get_by_id(outbox_id)
    if message is None:
        raise AppError("outbox_not_found", "Outbox message not found", status_code=404)
    if str(message.status) == "delivered":
        raise AppError(
            "outbox_already_delivered",
            "Delivered outbox messages cannot be requeued",
            status_code=409,
        )

    requeued = await repository.requeue(outbox_id)
    if requeued is None:
        raise AppError("outbox_not_found", "Outbox message not found", status_code=404)
    return OutboxActionResponse(
        message="Outbox message requeued",
        outbox=_outbox_to_response(requeued),
    )
