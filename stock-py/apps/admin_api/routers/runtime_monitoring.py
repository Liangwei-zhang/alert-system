from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from domains.admin.platform_metrics_service import PlatformRuntimeMetricsService
from domains.admin.runtime_metrics_service import RuntimeOperationalMetricsService
from infra.db.session import get_db_session
from infra.observability.runtime_monitoring import get_runtime_component, list_runtime_components

router = APIRouter(prefix="/v1/admin/runtime", tags=["admin", "runtime-monitoring"])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RuntimeComponentResponse(BaseModel):
    component_kind: str
    component_name: str
    status: str
    health: str
    last_heartbeat_at: str | None = None
    started_at: str | None = None
    expires_at: str | None = None
    ttl_seconds: int | None = None
    heartbeat_count: int = 0
    host: str | None = None
    pid: int | None = None
    metadata: dict = {}
    age_seconds: float | None = None
    is_expected: bool = False


class RuntimeComponentSummaryResponse(BaseModel):
    total: int
    healthy: int
    stale: int
    missing: int
    inactive: int
    error: int


class RuntimeComponentListResponse(BaseModel):
    summary: RuntimeComponentSummaryResponse
    components: list[RuntimeComponentResponse]


class RuntimeStatsResponse(BaseModel):
    recorded_at: str
    summary: RuntimeComponentSummaryResponse
    expected_components: int
    reporting_components: int
    coverage_percent: float
    by_kind: dict[str, int] = Field(default_factory=dict)
    by_status: dict[str, int] = Field(default_factory=dict)
    total_heartbeats: int
    avg_age_seconds: float | None = None
    max_age_seconds: float | None = None
    avg_ttl_seconds: float | None = None


class RuntimeHealthResponse(BaseModel):
    recorded_at: str
    status: str
    summary: RuntimeComponentSummaryResponse
    expected_components: int
    reporting_components: int
    coverage_percent: float
    missing_components: list[RuntimeComponentResponse] = Field(default_factory=list)
    stale_components: list[RuntimeComponentResponse] = Field(default_factory=list)
    error_components: list[RuntimeComponentResponse] = Field(default_factory=list)


class RuntimeMetricPointResponse(BaseModel):
    name: str
    value: float
    labels: dict[str, str] = Field(default_factory=dict)


class RuntimeMetricsResponse(BaseModel):
    recorded_at: str
    metrics: list[RuntimeMetricPointResponse]


class RuntimeAlertResponse(BaseModel):
    severity: str
    component: str
    summary: str
    observed_value: float | None = None
    threshold: float | None = None
    labels: dict[str, str] = Field(default_factory=dict)


class RuntimeAlertsResponse(BaseModel):
    recorded_at: str
    alerts: list[RuntimeAlertResponse]


def _coerce_metric_value(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _build_component_result_metrics(
    components: list[dict],
) -> list[RuntimeMetricPointResponse]:
    metrics: list[RuntimeMetricPointResponse] = []
    for component in components:
        metadata = dict(component.get("metadata") or {})
        last_result = metadata.get("last_result")
        if not isinstance(last_result, dict):
            continue
        for field_name, raw_value in sorted(last_result.items()):
            value = _coerce_metric_value(raw_value)
            if value is None:
                continue
            metrics.append(
                RuntimeMetricPointResponse(
                    name="runtime_component_last_result",
                    value=value,
                    labels={
                        "component_kind": str(component.get("component_kind") or "unknown"),
                        "component_name": str(component.get("component_name") or "unknown"),
                        "field": str(field_name),
                    },
                )
            )
    return metrics


def _to_response(component: dict) -> RuntimeComponentResponse:
    return RuntimeComponentResponse(**component)


def _build_summary(components: list[dict]) -> RuntimeComponentSummaryResponse:
    return RuntimeComponentSummaryResponse(
        total=len(components),
        healthy=sum(1 for component in components if component["health"] == "healthy"),
        stale=sum(1 for component in components if component["health"] == "stale"),
        missing=sum(1 for component in components if component["health"] == "missing"),
        inactive=sum(1 for component in components if component["health"] == "inactive"),
        error=sum(1 for component in components if component["health"] == "error"),
    )


def _build_runtime_stats_payload(components: list[dict]) -> RuntimeStatsResponse:
    now = utcnow().isoformat().replace("+00:00", "Z")
    summary = _build_summary(components)
    expected_components = sum(1 for component in components if bool(component.get("is_expected")))
    reporting_components = sum(
        1
        for component in components
        if bool(component.get("is_expected")) and component.get("health") != "missing"
    )
    coverage_percent = 100.0
    if expected_components > 0:
        coverage_percent = round((reporting_components / expected_components) * 100, 2)

    kind_counts = Counter(str(component["component_kind"]) for component in components)
    status_counts = Counter(str(component["status"]) for component in components)
    heartbeat_total = sum(int(component.get("heartbeat_count") or 0) for component in components)

    ages = [
        float(component["age_seconds"])
        for component in components
        if component.get("age_seconds") is not None
    ]
    ttls = [
        float(component["ttl_seconds"])
        for component in components
        if component.get("ttl_seconds") is not None
    ]

    return RuntimeStatsResponse(
        recorded_at=now,
        summary=summary,
        expected_components=expected_components,
        reporting_components=reporting_components,
        coverage_percent=coverage_percent,
        by_kind=dict(sorted(kind_counts.items())),
        by_status=dict(sorted(status_counts.items())),
        total_heartbeats=heartbeat_total,
        avg_age_seconds=(round(sum(ages) / len(ages), 2) if ages else None),
        max_age_seconds=(round(max(ages), 2) if ages else None),
        avg_ttl_seconds=(round(sum(ttls) / len(ttls), 2) if ttls else None),
    )


def _build_runtime_health_payload(components: list[dict]) -> RuntimeHealthResponse:
    stats = _build_runtime_stats_payload(components)
    if stats.summary.error > 0:
        status = "error"
    elif stats.summary.stale > 0 or stats.summary.missing > 0:
        status = "degraded"
    elif stats.summary.total == 0:
        status = "unknown"
    else:
        status = "healthy"

    return RuntimeHealthResponse(
        recorded_at=stats.recorded_at,
        status=status,
        summary=stats.summary,
        expected_components=stats.expected_components,
        reporting_components=stats.reporting_components,
        coverage_percent=stats.coverage_percent,
        missing_components=[
            _to_response(component) for component in components if component["health"] == "missing"
        ],
        stale_components=[
            _to_response(component) for component in components if component["health"] == "stale"
        ],
        error_components=[
            _to_response(component) for component in components if component["health"] == "error"
        ],
    )


def _build_runtime_metrics_payload(
    components: list[dict],
    *,
    operational_metrics: list[RuntimeMetricPointResponse] | None = None,
) -> RuntimeMetricsResponse:
    stats = _build_runtime_stats_payload(components)
    metrics: list[RuntimeMetricPointResponse] = [
        RuntimeMetricPointResponse(
            name="runtime_components_total", value=float(stats.summary.total)
        ),
        RuntimeMetricPointResponse(
            name="runtime_components_healthy", value=float(stats.summary.healthy)
        ),
        RuntimeMetricPointResponse(
            name="runtime_components_stale", value=float(stats.summary.stale)
        ),
        RuntimeMetricPointResponse(
            name="runtime_components_missing", value=float(stats.summary.missing)
        ),
        RuntimeMetricPointResponse(
            name="runtime_components_inactive", value=float(stats.summary.inactive)
        ),
        RuntimeMetricPointResponse(
            name="runtime_components_error", value=float(stats.summary.error)
        ),
        RuntimeMetricPointResponse(
            name="runtime_expected_components_total", value=float(stats.expected_components)
        ),
        RuntimeMetricPointResponse(
            name="runtime_reporting_components_total", value=float(stats.reporting_components)
        ),
        RuntimeMetricPointResponse(
            name="runtime_coverage_percent", value=float(stats.coverage_percent)
        ),
        RuntimeMetricPointResponse(
            name="runtime_heartbeats_total", value=float(stats.total_heartbeats)
        ),
    ]

    if stats.avg_age_seconds is not None:
        metrics.append(
            RuntimeMetricPointResponse(
                name="runtime_component_age_seconds_avg", value=float(stats.avg_age_seconds)
            )
        )
    if stats.max_age_seconds is not None:
        metrics.append(
            RuntimeMetricPointResponse(
                name="runtime_component_age_seconds_max", value=float(stats.max_age_seconds)
            )
        )
    if stats.avg_ttl_seconds is not None:
        metrics.append(
            RuntimeMetricPointResponse(
                name="runtime_component_ttl_seconds_avg", value=float(stats.avg_ttl_seconds)
            )
        )

    for component_kind, count in stats.by_kind.items():
        metrics.append(
            RuntimeMetricPointResponse(
                name="runtime_components_by_kind",
                value=float(count),
                labels={"component_kind": component_kind},
            )
        )
    for lifecycle_status, count in stats.by_status.items():
        metrics.append(
            RuntimeMetricPointResponse(
                name="runtime_components_by_status",
                value=float(count),
                labels={"status": lifecycle_status},
            )
        )

    metrics.extend(_build_component_result_metrics(components))
    metrics.extend(operational_metrics or [])

    return RuntimeMetricsResponse(recorded_at=stats.recorded_at, metrics=metrics)


async def _collect_runtime_operational_metrics(
    *,
    component_kind: str | None,
    db: AsyncSession,
) -> list[RuntimeMetricPointResponse]:
    if component_kind == "scheduler":
        return []
    service = RuntimeOperationalMetricsService(db)
    return [
        RuntimeMetricPointResponse(name=point.name, value=point.value, labels=point.labels)
        for point in await service.collect_metric_points()
    ]


async def _collect_platform_operational_metrics() -> list[RuntimeMetricPointResponse]:
    service = PlatformRuntimeMetricsService()
    return [
        RuntimeMetricPointResponse(name=point.name, value=point.value, labels=point.labels)
        for point in await service.collect_metric_points()
    ]


async def _collect_runtime_alerts() -> list[RuntimeAlertResponse]:
    service = PlatformRuntimeMetricsService()
    return [
        RuntimeAlertResponse(
            severity=alert.severity,
            component=alert.component,
            summary=alert.summary,
            observed_value=alert.observed_value,
            threshold=alert.threshold,
            labels=alert.labels,
        )
        for alert in await service.collect_alerts()
    ]


@router.get("/components", response_model=RuntimeComponentListResponse)
async def list_components(
    component_kind: str | None = Query(
        None,
        pattern="^(scheduler|worker)$",
        description="Filter by runtime component kind",
    ),
    health: str | None = Query(
        None,
        pattern="^(healthy|stale|missing|inactive|error|unknown)$",
        description="Filter by computed health",
    ),
    status: str | None = Query(None, description="Filter by raw lifecycle status"),
) -> RuntimeComponentListResponse:
    components = await list_runtime_components(component_kind=component_kind)

    if health is not None:
        components = [component for component in components if component["health"] == health]
    if status is not None:
        normalized_status = str(status).strip().lower()
        components = [
            component for component in components if component["status"] == normalized_status
        ]

    return RuntimeComponentListResponse(
        summary=_build_summary(components),
        components=[_to_response(component) for component in components],
    )


@router.get("/stats", response_model=RuntimeStatsResponse)
async def get_runtime_stats(
    component_kind: str | None = Query(
        None,
        pattern="^(scheduler|worker)$",
        description="Filter by runtime component kind",
    ),
) -> RuntimeStatsResponse:
    components = await list_runtime_components(component_kind=component_kind)
    return _build_runtime_stats_payload(components)


@router.get("/health", response_model=RuntimeHealthResponse)
async def get_runtime_health(
    component_kind: str | None = Query(
        None,
        pattern="^(scheduler|worker)$",
        description="Filter by runtime component kind",
    ),
) -> RuntimeHealthResponse:
    components = await list_runtime_components(component_kind=component_kind)
    return _build_runtime_health_payload(components)


@router.get("/metrics", response_model=RuntimeMetricsResponse)
async def get_runtime_metrics(
    component_kind: str | None = Query(
        None,
        pattern="^(scheduler|worker)$",
        description="Filter by runtime component kind",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> RuntimeMetricsResponse:
    components = await list_runtime_components(component_kind=component_kind)
    operational_metrics = await _collect_runtime_operational_metrics(
        component_kind=component_kind,
        db=db,
    )
    platform_metrics = await _collect_platform_operational_metrics()
    return _build_runtime_metrics_payload(
        components,
        operational_metrics=[*operational_metrics, *platform_metrics],
    )


@router.get("/alerts", response_model=RuntimeAlertsResponse)
async def get_runtime_alerts() -> RuntimeAlertsResponse:
    return RuntimeAlertsResponse(
        recorded_at=utcnow().isoformat().replace("+00:00", "Z"),
        alerts=await _collect_runtime_alerts(),
    )


@router.get(
    "/components/{component_kind}/{component_name}", response_model=RuntimeComponentResponse
)
async def get_component(component_kind: str, component_name: str) -> RuntimeComponentResponse:
    component = await get_runtime_component(component_kind, component_name)
    if component is None:
        raise HTTPException(status_code=404, detail="Runtime component not found")
    return _to_response(component)
