"""
Pydantic schemas for TradingAgents domain.
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field, field_validator


class SubmitTradingAgentsRequest(BaseModel):
    """Request schema for submitting a TradingAgents analysis job."""

    request_id: str = Field(..., min_length=1, max_length=64, description="Unique request ID")
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    analysis_date: datetime = Field(..., description="Analysis date")
    selected_analysts: Optional[List[str]] = Field(
        default=None, description="List of analysts to use"
    )
    trigger_type: str = Field(
        default="manual",
        pattern="^(scanner|manual|position_review|scheduled)$",
        description="Trigger type",
    )
    trigger_context: Optional[dict] = Field(default=None, description="Additional trigger context")
    debug: Optional[bool] = Field(default=None, description="Debug mode forwarded to TradingAgents")
    config_overrides: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional TradingAgents config overrides",
    )
    publish_video: Optional[bool] = Field(
        default=None,
        description="Optional report video generation flag",
    )
    video_privacy_status: Optional[str] = Field(
        default=None,
        pattern="^(public|unlisted|private)$",
        description="Video privacy when publish_video is enabled",
    )

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        return v.upper()


class TradingAgentsProjection(BaseModel):
    """Projection of TradingAgents analysis result."""

    request_id: str
    job_id: Optional[str] = None
    tradingagents_status: str = Field(
        ...,
        description="pending|submitted|running|completed|failed|timeout|queued|succeeded|canceled",
    )
    final_action: Optional[str] = Field(default=None, description="buy|sell|hold|no_action|unknown")
    decision_summary: Optional[str] = None
    result_payload: Optional[dict] = None

    model_config = None


class SubmitTradingAgentsResponse(BaseModel):
    """Response after submitting a job."""

    request_id: str
    job_id: Optional[str] = None
    status: str
    message: str


TradingAgentsSubmitResponse = SubmitTradingAgentsResponse


class TradingAgentsJobTerminalEvent(BaseModel):
    """Webhook payload for job terminal event."""

    request_id: str
    job_id: str
    status: Optional[str] = Field(
        default=None,
        description="queued|running|succeeded|failed|canceled|completed|timeout",
    )
    tradingagents_status: Optional[str] = Field(
        default=None,
        description="queued|running|succeeded|failed|canceled",
    )
    final_action: Optional[str] = None
    decision_summary: Optional[str] = None
    result_payload: Optional[dict] = None
    timestamp: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class TradingAgentsAnalysisListQuery(BaseModel):
    """Query parameters for listing analyses."""

    status: Optional[str] = Field(
        default=None, pattern="^(pending|submitted|running|completed|failed|timeout)$"
    )
    ticker: Optional[str] = None
    trigger_type: Optional[str] = Field(
        default=None, pattern="^(scanner|manual|position_review|scheduled)$"
    )
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class TradingAgentsAnalysisResponse(BaseModel):
    """Response for a single analysis record."""

    id: int
    request_id: str
    job_id: Optional[str]
    ticker: str
    analysis_date: datetime
    selected_analysts: Optional[List[str]] = None
    trigger_type: str
    trigger_context: Optional[dict] = None
    tradingagents_status: str
    final_action: Optional[str] = None
    decision_summary: Optional[str] = None
    submitted_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    delayed_at: Optional[datetime] = None
    created_at: datetime
    poll_count: int
    webhook_received: bool

    model_config = None


class ReconcileDelayedResponse(BaseModel):
    """Response for reconcile delayed jobs."""

    processed_count: int
    reconciled_count: int
    failed_count: int
    message: str
