from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NotificationListQuery(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=20, ge=1, le=50)


class RegisterPushDeviceRequest(BaseModel):
    device_id: str = Field(min_length=1, max_length=120)
    endpoint: str = Field(min_length=1, max_length=4096)
    provider: str = Field(default="webpush", max_length=20)
    public_key: str | None = Field(default=None, max_length=2048)
    auth_key: str | None = Field(default=None, max_length=2048)
    user_agent: str | None = Field(default=None, max_length=512)
    locale: str | None = Field(default=None, max_length=32)
    timezone: str | None = Field(default=None, max_length=64)
    extra: dict | None = None


class NotificationItemResponse(BaseModel):
    id: str
    signal_id: str | None = None
    trade_id: str | None = None
    type: str
    title: str
    body: str
    is_read: bool
    created_at: datetime
    receipt_id: str | None = None
    ack_required: bool = False
    ack_deadline_at: datetime | None = None
    opened_at: datetime | None = None
    acknowledged_at: datetime | None = None
    last_delivery_channel: str | None = None
    last_delivery_status: str | None = None
    escalation_level: int = 0


class NotificationListResponse(BaseModel):
    items: list[NotificationItemResponse]
    next_cursor: str | None = None


class PushDeviceResponse(BaseModel):
    id: str
    device_id: str
    endpoint: str
    provider: str
    is_active: bool
    last_seen_at: datetime
    created_at: datetime


class PushConfigResponse(BaseModel):
    enabled: bool
    public_key: str | None = None
    subject: str | None = None


class NotificationCommandResponse(BaseModel):
    message: str


class NotificationAcknowledgeResponse(BaseModel):
    message: str
    acknowledged: bool
    acknowledged_at: datetime | None = None


class TestPushResponse(BaseModel):
    delivered: bool
    invalidated: bool = False
    error: str | None = None
