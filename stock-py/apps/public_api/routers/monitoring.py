from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from infra.core.config import Settings, get_settings
from infra.core.errors import AppError
from infra.observability.metrics import get_http_request_tracker, get_metrics_registry

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


class MonitoringEndpointResponse(BaseModel):
    method: str
    path: str
    requests: int
    errors: int
    last_status_code: int | None = None
    p50_latency_ms: float | None = None
    p95_latency_ms: float | None = None
    p99_latency_ms: float | None = None


class MonitoringStatsResponse(BaseModel):
    requests: int
    errors: int
    uptime_seconds: float
    endpoints: dict[str, MonitoringEndpointResponse]
    timestamp: str


class MonitoringResetResponse(BaseModel):
    ok: bool
    message: str


def _configured_secret(settings: Settings) -> str:
    return str(
        settings.internal_sidecar_secret or settings.internal_signal_ingest_secret or ""
    ).strip()


def _bearer_token(authorization: str | None) -> str:
    value = str(authorization or "").strip()
    if not value.lower().startswith("bearer "):
        return ""
    return value[7:].strip()


async def require_internal_monitoring_secret(
    authorization: str | None = Header(default=None),
    x_internal_sidecar_secret: str | None = Header(default=None),
) -> None:
    settings = get_settings()
    configured_secret = _configured_secret(settings)
    if not configured_secret:
        if settings.debug:
            return
        raise AppError(
            "internal_monitoring_secret_missing",
            "Internal monitoring secret is not configured",
            status_code=503,
        )
    if x_internal_sidecar_secret == configured_secret:
        return
    if _bearer_token(authorization) == configured_secret:
        return
    raise AppError(
        "internal_monitoring_forbidden",
        "Invalid internal monitoring secret",
        status_code=403,
    )


@router.get("/stats", response_model=MonitoringStatsResponse)
async def get_monitoring_stats(
    _authorized: None = Depends(require_internal_monitoring_secret),
) -> MonitoringStatsResponse:
    payload = get_http_request_tracker("public-api").snapshot()
    return MonitoringStatsResponse(**payload)


@router.get("/metrics", response_class=PlainTextResponse)
async def get_monitoring_metrics(
    _authorized: None = Depends(require_internal_monitoring_secret),
) -> PlainTextResponse:
    parts = [
        get_metrics_registry().prometheus_text("stock_signal"),
        get_http_request_tracker("public-api").prometheus_text("stock_signal"),
    ]
    content = "\n".join(part.strip() for part in parts if part.strip()).strip() + "\n"
    return PlainTextResponse(content, media_type="text/plain; version=0.0.4; charset=utf-8")


@router.post("/reset", response_model=MonitoringResetResponse)
async def reset_monitoring_metrics(
    _authorized: None = Depends(require_internal_monitoring_secret),
) -> MonitoringResetResponse:
    settings = get_settings()
    if str(settings.environment).strip().lower() == "production":
        raise AppError(
            "monitoring_reset_disabled",
            "Metric reset is disabled in production",
            status_code=403,
        )

    get_metrics_registry().reset()
    get_http_request_tracker("public-api").reset()
    return MonitoringResetResponse(ok=True, message="Metrics reset complete")