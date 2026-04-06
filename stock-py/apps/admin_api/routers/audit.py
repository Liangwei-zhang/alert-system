from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db.session import get_db_session
from infra.events.outbox import EventOutboxRepository

router = APIRouter(prefix="/v1/admin/audit", tags=["admin", "audit"])


class AdminAuditEventResponse(BaseModel):
    id: str
    topic: str
    event_key: str | None = None
    status: str
    entity: str | None = None
    entity_id: str | None = None
    action: str | None = None
    source: str | None = None
    request_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int
    last_error: str | None = None
    occurred_at: datetime
    published_at: datetime | None = None
    created_at: datetime


class AdminAuditEventListResponse(BaseModel):
    data: list[AdminAuditEventResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


def _to_response(record) -> AdminAuditEventResponse:
    payload = dict(getattr(record, "payload", {}) or {})
    headers = dict(getattr(record, "headers", {}) or {})
    return AdminAuditEventResponse(
        id=str(record.id),
        topic=str(record.topic),
        event_key=str(record.event_key) if getattr(record, "event_key", None) else None,
        status=str(record.status),
        entity=str(payload.get("entity")) if payload.get("entity") is not None else None,
        entity_id=str(payload.get("entity_id")) if payload.get("entity_id") is not None else None,
        action=str(payload.get("action")) if payload.get("action") is not None else None,
        source=str(payload.get("source")) if payload.get("source") is not None else None,
        request_id=(
            str(headers.get("request_id") or payload.get("request_id"))
            if headers.get("request_id") or payload.get("request_id")
            else None
        ),
        payload=payload,
        headers=headers,
        attempt_count=int(getattr(record, "attempt_count", 0) or 0),
        last_error=str(record.last_error) if getattr(record, "last_error", None) else None,
        occurred_at=record.occurred_at,
        published_at=getattr(record, "published_at", None),
        created_at=record.created_at,
    )


@router.get("", response_model=AdminAuditEventListResponse)
async def list_audit_events(
    entity: str | None = Query(None, description="Filter by entity"),
    entity_id: str | None = Query(None, description="Filter by entity id"),
    action: str | None = Query(None, description="Filter by action"),
    source: str | None = Query(None, description="Filter by source"),
    status: str | None = Query(
        None,
        pattern="^(pending|published)$",
        description="Filter by outbox status",
    ),
    request_id: str | None = Query(None, description="Filter by request id"),
    limit: int = Query(50, ge=1, le=500, description="Results limit"),
    offset: int = Query(0, ge=0, description="Results offset"),
    db: AsyncSession = Depends(get_db_session),
) -> AdminAuditEventListResponse:
    repository = EventOutboxRepository(db)
    records = await repository.list_audit_events(
        limit=limit,
        offset=offset,
        entity=entity,
        entity_id=entity_id,
        action=action,
        source=source,
        status=status,
        request_id=request_id,
    )
    total = await repository.count_audit_events(
        entity=entity,
        entity_id=entity_id,
        action=action,
        source=source,
        status=status,
        request_id=request_id,
    )
    return AdminAuditEventListResponse(
        data=[_to_response(record) for record in records],
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + len(records)) < total,
    )
