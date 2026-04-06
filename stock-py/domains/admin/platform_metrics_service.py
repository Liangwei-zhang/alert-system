from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from urllib.parse import urlparse, urlunparse

from infra.analytics.clickhouse_client import get_clickhouse_client
from infra.cache.redis_client import get_redis
from infra.core.config import Settings, get_settings
from infra.db.session import build_database_url
from infra.observability.external_operation_metrics import (
    ExternalOperationSnapshot,
    get_external_operation_snapshot,
)
from infra.storage.object_storage import get_object_storage_client

from .runtime_metrics_service import RuntimeOperationalMetricPoint


def _format_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or default)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class RuntimePlatformAlert:
    severity: str
    component: str
    summary: str
    observed_value: float | None = None
    threshold: float | None = None
    labels: dict[str, str] = field(default_factory=dict)


class PlatformRuntimeMetricsService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        redis_info_provider=None,
        pgbouncer_stats_provider=None,
        broker_lag_provider=None,
        clickhouse_ping_provider=None,
        object_storage_ping_provider=None,
        operation_snapshot_provider=None,
    ) -> None:
        self.settings = settings or get_settings()
        self.redis_info_provider = redis_info_provider
        self.pgbouncer_stats_provider = pgbouncer_stats_provider
        self.broker_lag_provider = broker_lag_provider
        self.clickhouse_ping_provider = clickhouse_ping_provider
        self.object_storage_ping_provider = object_storage_ping_provider
        self.operation_snapshot_provider = (
            operation_snapshot_provider or get_external_operation_snapshot
        )

    async def collect_metric_points(self) -> list[RuntimeOperationalMetricPoint]:
        snapshots = await self._collect_snapshots()
        metrics: list[RuntimeOperationalMetricPoint] = []
        window_label = {"window_minutes": str(self.settings.runtime_metrics_window_minutes)}

        redis_snapshot = snapshots.get("redis")
        if redis_snapshot is not None:
            metrics.append(
                RuntimeOperationalMetricPoint(
                    name="redis_available",
                    value=1.0 if redis_snapshot.get("available") else 0.0,
                )
            )
            if redis_snapshot.get("available"):
                metrics.extend(
                    [
                        RuntimeOperationalMetricPoint(
                            name="redis_used_memory_bytes",
                            value=float(redis_snapshot.get("used_memory") or 0),
                        ),
                        RuntimeOperationalMetricPoint(
                            name="redis_evicted_keys_total",
                            value=float(redis_snapshot.get("evicted_keys") or 0),
                        ),
                    ]
                )
                maxmemory = int(redis_snapshot.get("maxmemory") or 0)
                if maxmemory > 0:
                    metrics.append(
                        RuntimeOperationalMetricPoint(
                            name="redis_maxmemory_bytes",
                            value=float(maxmemory),
                        )
                    )
                    metrics.append(
                        RuntimeOperationalMetricPoint(
                            name="redis_memory_utilization_percent",
                            value=float(redis_snapshot.get("utilization_percent") or 0.0),
                        )
                    )

        broker_snapshot = snapshots.get("broker")
        if broker_snapshot is not None:
            broker_labels = {
                "backend": str(broker_snapshot.get("backend") or "unknown"),
                "group": str(broker_snapshot.get("group_name") or "unknown"),
            }
            metrics.append(
                RuntimeOperationalMetricPoint(
                    name="event_broker_available",
                    value=1.0 if broker_snapshot.get("available") else 0.0,
                    labels=broker_labels,
                )
            )
            if broker_snapshot.get("available"):
                metrics.extend(
                    [
                        RuntimeOperationalMetricPoint(
                            name="event_broker_consumer_lag_total",
                            value=float(broker_snapshot.get("lag_total") or 0),
                            labels=broker_labels,
                        ),
                        RuntimeOperationalMetricPoint(
                            name="event_broker_partition_lag_max",
                            value=float(broker_snapshot.get("max_partition_lag") or 0),
                            labels=broker_labels,
                        ),
                        RuntimeOperationalMetricPoint(
                            name="event_broker_partitions_total",
                            value=float(broker_snapshot.get("partitions") or 0),
                            labels=broker_labels,
                        ),
                    ]
                )

        pgbouncer_snapshot = snapshots.get("pgbouncer")
        if pgbouncer_snapshot is not None:
            labels = {"database": str(pgbouncer_snapshot.get("database") or "unknown")}
            metrics.append(
                RuntimeOperationalMetricPoint(
                    name="pgbouncer_available",
                    value=1.0 if pgbouncer_snapshot.get("available") else 0.0,
                    labels=labels,
                )
            )
            if pgbouncer_snapshot.get("available"):
                metrics.extend(
                    [
                        RuntimeOperationalMetricPoint(
                            name="pgbouncer_clients_active",
                            value=float(pgbouncer_snapshot.get("cl_active") or 0),
                            labels=labels,
                        ),
                        RuntimeOperationalMetricPoint(
                            name="pgbouncer_clients_waiting",
                            value=float(pgbouncer_snapshot.get("cl_waiting") or 0),
                            labels=labels,
                        ),
                        RuntimeOperationalMetricPoint(
                            name="pgbouncer_servers_active",
                            value=float(pgbouncer_snapshot.get("sv_active") or 0),
                            labels=labels,
                        ),
                        RuntimeOperationalMetricPoint(
                            name="pgbouncer_servers_idle",
                            value=float(pgbouncer_snapshot.get("sv_idle") or 0),
                            labels=labels,
                        ),
                    ]
                )

        clickhouse_snapshot = snapshots.get("clickhouse")
        if clickhouse_snapshot is not None:
            metrics.append(
                RuntimeOperationalMetricPoint(
                    name="clickhouse_available",
                    value=1.0 if clickhouse_snapshot.get("available") else 0.0,
                )
            )

        object_storage_snapshot = snapshots.get("object_storage")
        if object_storage_snapshot is not None:
            metrics.append(
                RuntimeOperationalMetricPoint(
                    name="object_storage_available",
                    value=1.0 if object_storage_snapshot.get("available") else 0.0,
                )
            )

        clickhouse_writes = snapshots.get("clickhouse_writes")
        if clickhouse_writes is not None:
            metrics.extend(
                self._build_operation_metrics("clickhouse_write", clickhouse_writes, window_label)
            )

        object_storage_archive = snapshots.get("object_storage_archive")
        if object_storage_archive is not None:
            metrics.extend(
                self._build_operation_metrics(
                    "object_storage_archive",
                    object_storage_archive,
                    window_label,
                )
            )

        return metrics

    async def collect_alerts(self) -> list[RuntimePlatformAlert]:
        snapshots = await self._collect_snapshots()
        alerts: list[RuntimePlatformAlert] = []

        broker_snapshot = snapshots.get("broker")
        if broker_snapshot is not None:
            if not broker_snapshot.get("available"):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="critical",
                        component="event-broker",
                        summary=f"Broker lag probe unavailable: {broker_snapshot.get('error') or 'unknown error'}",
                    )
                )
            elif float(broker_snapshot.get("lag_total") or 0) >= float(
                self.settings.runtime_alert_broker_lag_threshold
            ):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="warning",
                        component="event-broker",
                        summary="Broker consumer lag exceeded threshold",
                        observed_value=float(broker_snapshot.get("lag_total") or 0),
                        threshold=float(self.settings.runtime_alert_broker_lag_threshold),
                        labels={
                            "backend": str(broker_snapshot.get("backend") or "unknown"),
                            "group": str(broker_snapshot.get("group_name") or "unknown"),
                        },
                    )
                )

        pgbouncer_snapshot = snapshots.get("pgbouncer")
        if pgbouncer_snapshot is not None:
            if not pgbouncer_snapshot.get("available"):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="warning",
                        component="pgbouncer",
                        summary=f"PgBouncer probe unavailable: {pgbouncer_snapshot.get('error') or 'unknown error'}",
                    )
                )
            elif float(pgbouncer_snapshot.get("cl_waiting") or 0) >= float(
                self.settings.runtime_alert_pgbouncer_waiting_clients_threshold
            ):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="warning",
                        component="pgbouncer",
                        summary="PgBouncer waiting clients exceeded threshold",
                        observed_value=float(pgbouncer_snapshot.get("cl_waiting") or 0),
                        threshold=float(
                            self.settings.runtime_alert_pgbouncer_waiting_clients_threshold
                        ),
                        labels={"database": str(pgbouncer_snapshot.get("database") or "unknown")},
                    )
                )

        redis_snapshot = snapshots.get("redis")
        if redis_snapshot is not None:
            if not redis_snapshot.get("available"):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="critical",
                        component="redis",
                        summary=f"Redis probe unavailable: {redis_snapshot.get('error') or 'unknown error'}",
                    )
                )
            elif float(redis_snapshot.get("utilization_percent") or 0.0) >= float(
                self.settings.runtime_alert_redis_memory_percent_threshold
            ):
                alerts.append(
                    RuntimePlatformAlert(
                        severity="warning",
                        component="redis",
                        summary="Redis memory usage exceeded threshold",
                        observed_value=float(redis_snapshot.get("utilization_percent") or 0.0),
                        threshold=float(self.settings.runtime_alert_redis_memory_percent_threshold),
                    )
                )

        clickhouse_snapshot = snapshots.get("clickhouse")
        if clickhouse_snapshot is not None and not clickhouse_snapshot.get("available"):
            alerts.append(
                RuntimePlatformAlert(
                    severity="critical",
                    component="clickhouse",
                    summary=f"ClickHouse readiness probe failed: {clickhouse_snapshot.get('error') or 'unknown error'}",
                )
            )

        object_storage_snapshot = snapshots.get("object_storage")
        if object_storage_snapshot is not None and not object_storage_snapshot.get("available"):
            alerts.append(
                RuntimePlatformAlert(
                    severity="critical",
                    component="object-storage",
                    summary=f"Object storage readiness probe failed: {object_storage_snapshot.get('error') or 'unknown error'}",
                )
            )

        clickhouse_writes = snapshots.get("clickhouse_writes")
        if (
            clickhouse_writes is not None
            and clickhouse_writes.failure_recent > 0
            and clickhouse_writes.failure_rate_percent
            >= float(self.settings.runtime_alert_clickhouse_write_failure_rate_threshold)
        ):
            alerts.append(
                RuntimePlatformAlert(
                    severity="critical",
                    component="clickhouse",
                    summary="ClickHouse write failure rate exceeded threshold",
                    observed_value=clickhouse_writes.failure_rate_percent,
                    threshold=float(
                        self.settings.runtime_alert_clickhouse_write_failure_rate_threshold
                    ),
                    labels={"window_minutes": str(self.settings.runtime_metrics_window_minutes)},
                )
            )

        object_storage_archive = snapshots.get("object_storage_archive")
        if (
            object_storage_archive is not None
            and object_storage_archive.failure_recent > 0
            and object_storage_archive.failure_rate_percent
            >= float(self.settings.runtime_alert_object_storage_archive_failure_rate_threshold)
        ):
            alerts.append(
                RuntimePlatformAlert(
                    severity="critical",
                    component="object-storage-archive",
                    summary="Object storage archive failure rate exceeded threshold",
                    observed_value=object_storage_archive.failure_rate_percent,
                    threshold=float(
                        self.settings.runtime_alert_object_storage_archive_failure_rate_threshold
                    ),
                    labels={"window_minutes": str(self.settings.runtime_metrics_window_minutes)},
                )
            )

        return alerts

    def _build_operation_metrics(
        self,
        metric_prefix: str,
        snapshot: ExternalOperationSnapshot,
        labels: dict[str, str],
    ) -> list[RuntimeOperationalMetricPoint]:
        return [
            RuntimeOperationalMetricPoint(
                name=f"{metric_prefix}_window_attempts_total",
                value=float(snapshot.attempts_recent),
                labels=dict(labels),
            ),
            RuntimeOperationalMetricPoint(
                name=f"{metric_prefix}_window_failures_total",
                value=float(snapshot.failure_recent),
                labels=dict(labels),
            ),
            RuntimeOperationalMetricPoint(
                name=f"{metric_prefix}_failure_rate_percent",
                value=float(snapshot.failure_rate_percent),
                labels=dict(labels),
            ),
        ]

    async def _collect_snapshots(self) -> dict[str, object]:
        window_seconds = max(int(self.settings.runtime_metrics_window_minutes) * 60, 60)
        results = await asyncio.gather(
            self._load_redis_snapshot(),
            self._load_broker_snapshot(),
            self._load_pgbouncer_snapshot(),
            self._load_clickhouse_snapshot(),
            self._load_object_storage_snapshot(),
            self.operation_snapshot_provider(
                "clickhouse", "insert_rows", window_seconds=window_seconds
            ),
            self.operation_snapshot_provider(
                "object_storage_archive",
                "put_bytes",
                window_seconds=window_seconds,
            ),
        )
        return {
            "redis": results[0],
            "broker": results[1],
            "pgbouncer": results[2],
            "clickhouse": results[3],
            "object_storage": results[4],
            "clickhouse_writes": results[5],
            "object_storage_archive": results[6],
        }

    async def _load_redis_snapshot(self) -> dict[str, object]:
        try:
            info = (
                await self.redis_info_provider()
                if self.redis_info_provider is not None
                else await self._default_redis_info_provider()
            )
        except Exception as exc:
            return {"available": False, "error": _format_error(exc)}

        used_memory = _safe_int(info.get("used_memory"))
        maxmemory = _safe_int(info.get("maxmemory"))
        utilization_percent = 0.0
        if maxmemory > 0:
            utilization_percent = round((used_memory / maxmemory) * 100, 2)
        return {
            "available": True,
            "used_memory": used_memory,
            "maxmemory": maxmemory,
            "utilization_percent": utilization_percent,
            "evicted_keys": _safe_int(info.get("evicted_keys")),
        }

    async def _load_broker_snapshot(self) -> dict[str, object] | None:
        try:
            return (
                await self.broker_lag_provider()
                if self.broker_lag_provider is not None
                else await self._default_broker_lag_provider()
            )
        except Exception as exc:
            return {
                "available": False,
                "backend": self.settings.event_broker_backend,
                "group_name": self.settings.event_broker_group_name,
                "error": _format_error(exc),
            }

    async def _load_pgbouncer_snapshot(self) -> dict[str, object] | None:
        admin_dsn = self._resolve_pgbouncer_admin_dsn()
        if not admin_dsn:
            return None
        try:
            return (
                await self.pgbouncer_stats_provider(admin_dsn)
                if self.pgbouncer_stats_provider is not None
                else await self._default_pgbouncer_stats_provider(admin_dsn)
            )
        except Exception as exc:
            return {"available": False, "error": _format_error(exc), "database": "stock"}

    async def _load_clickhouse_snapshot(self) -> dict[str, object] | None:
        if self.settings.analytics_backend != "clickhouse":
            return None
        try:
            payload = (
                await self.clickhouse_ping_provider()
                if self.clickhouse_ping_provider is not None
                else await get_clickhouse_client().ping()
            )
            return {"available": True, **dict(payload or {})}
        except Exception as exc:
            return {"available": False, "error": _format_error(exc)}

    async def _load_object_storage_snapshot(self) -> dict[str, object] | None:
        if self.settings.object_storage_backend != "s3":
            return None
        try:
            payload = (
                await self.object_storage_ping_provider()
                if self.object_storage_ping_provider is not None
                else await get_object_storage_client().ping()
            )
            return {"available": True, **dict(payload or {})}
        except Exception as exc:
            return {"available": False, "error": _format_error(exc)}

    async def _default_redis_info_provider(self) -> dict[str, object]:
        client = await get_redis()
        return dict(await client.info())

    async def _default_broker_lag_provider(self) -> dict[str, object]:
        if self.settings.event_broker_backend == "redis":
            client = await get_redis()
            groups = await client.xinfo_groups(self.settings.event_broker_stream_name)
            group = next(
                (
                    item
                    for item in groups
                    if str(item.get("name")) == self.settings.event_broker_group_name
                ),
                None,
            )
            pending = _safe_int((group or {}).get("pending"))
            consumers = _safe_int((group or {}).get("consumers"))
            return {
                "available": True,
                "backend": "redis",
                "group_name": self.settings.event_broker_group_name,
                "lag_total": pending,
                "max_partition_lag": pending,
                "partitions": max(consumers, 1 if group else 0),
            }

        return await asyncio.to_thread(self._collect_kafka_lag_sync)

    def _collect_kafka_lag_sync(self) -> dict[str, object]:
        try:
            from kafka import KafkaConsumer, TopicPartition
        except ImportError as exc:
            raise RuntimeError("Kafka lag metrics require kafka-python") from exc

        consumer = KafkaConsumer(
            bootstrap_servers=[
                item.strip()
                for item in self.settings.event_broker_kafka_bootstrap_servers.split(",")
                if item.strip()
            ],
            group_id=self.settings.event_broker_group_name,
            enable_auto_commit=False,
            client_id="runtime-monitoring",
            api_version_auto_timeout_ms=3000,
            request_timeout_ms=5000,
        )
        try:
            partitions = sorted(
                consumer.partitions_for_topic(self.settings.event_broker_kafka_topic) or []
            )
            topic_partitions = [
                TopicPartition(self.settings.event_broker_kafka_topic, partition)
                for partition in partitions
            ]
            if not topic_partitions:
                return {
                    "available": True,
                    "backend": "kafka",
                    "group_name": self.settings.event_broker_group_name,
                    "lag_total": 0,
                    "max_partition_lag": 0,
                    "partitions": 0,
                }
            consumer.assign(topic_partitions)
            end_offsets = consumer.end_offsets(topic_partitions)
            lag_total = 0
            max_partition_lag = 0
            for topic_partition in topic_partitions:
                end_offset = _safe_int(end_offsets.get(topic_partition))
                committed = _safe_int(consumer.committed(topic_partition))
                lag = max(end_offset - committed, 0)
                lag_total += lag
                max_partition_lag = max(max_partition_lag, lag)
            return {
                "available": True,
                "backend": "kafka",
                "group_name": self.settings.event_broker_group_name,
                "lag_total": lag_total,
                "max_partition_lag": max_partition_lag,
                "partitions": len(topic_partitions),
            }
        finally:
            consumer.close()

    async def _default_pgbouncer_stats_provider(self, admin_dsn: str) -> dict[str, object]:
        try:
            import asyncpg
        except ImportError as exc:
            raise RuntimeError("PgBouncer metrics require asyncpg") from exc

        connection = await asyncpg.connect(dsn=admin_dsn, timeout=3)
        try:
            rows = await connection.fetch("SHOW POOLS")
        finally:
            await connection.close()

        database_name = urlparse(build_database_url(self.settings)).path.lstrip("/") or "stock"
        snapshot = {
            "available": True,
            "database": database_name,
            "cl_active": 0,
            "cl_waiting": 0,
            "sv_active": 0,
            "sv_idle": 0,
        }
        for row in rows:
            if str(row.get("database") or "") != database_name:
                continue
            snapshot["cl_active"] += _safe_int(row.get("cl_active"))
            snapshot["cl_waiting"] += _safe_int(row.get("cl_waiting"))
            snapshot["sv_active"] += _safe_int(row.get("sv_active"))
            snapshot["sv_idle"] += _safe_int(row.get("sv_idle"))
        return snapshot

    def _resolve_pgbouncer_admin_dsn(self) -> str:
        explicit = str(self.settings.pgbouncer_admin_url or "").strip()
        if explicit:
            return explicit
        if self.settings.database_pool_mode != "pgbouncer":
            return ""
        parsed = urlparse(build_database_url(self.settings))
        if not parsed.scheme:
            return ""
        return urlunparse(
            parsed._replace(
                scheme=parsed.scheme.replace("+asyncpg", ""),
                path="/pgbouncer",
            )
        )
