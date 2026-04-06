import unittest

from domains.admin.platform_metrics_service import PlatformRuntimeMetricsService
from infra.core.config import Settings
from infra.observability.external_operation_metrics import ExternalOperationSnapshot


class PlatformRuntimeMetricsServiceTest(unittest.IsolatedAsyncioTestCase):
    async def test_collect_metric_points_emits_platform_capacity_and_failure_metrics(self) -> None:
        settings = Settings(
            database_url="postgresql+asyncpg://stock_py:stock_py@pgbouncer:6432/stock_py",
            database_pool_mode="pgbouncer",
            pgbouncer_admin_url="postgresql://stock_py:stock_py@pgbouncer:6432/pgbouncer",
            analytics_backend="clickhouse",
            object_storage_backend="s3",
            runtime_metrics_window_minutes=15,
        )

        async def redis_info_provider() -> dict[str, object]:
            return {"used_memory": 512, "maxmemory": 1024, "evicted_keys": 3}

        async def broker_lag_provider() -> dict[str, object]:
            return {
                "available": True,
                "backend": "kafka",
                "group_name": "stock-py.dispatchers",
                "lag_total": 27,
                "max_partition_lag": 11,
                "partitions": 3,
            }

        async def pgbouncer_stats_provider(admin_dsn: str) -> dict[str, object]:
            self.assertEqual(admin_dsn, "postgresql://stock_py:stock_py@pgbouncer:6432/pgbouncer")
            return {
                "available": True,
                "database": "stock_py",
                "cl_active": 9,
                "cl_waiting": 2,
                "sv_active": 4,
                "sv_idle": 6,
            }

        async def clickhouse_ping_provider() -> dict[str, object]:
            return {"backend": "clickhouse", "database": "stock_py"}

        async def object_storage_ping_provider() -> dict[str, object]:
            return {"backend": "s3", "bucket": "stock-py"}

        async def operation_snapshot_provider(
            component: str,
            operation: str,
            *,
            window_seconds: int,
        ) -> ExternalOperationSnapshot:
            self.assertEqual(window_seconds, 900)
            if component == "clickhouse":
                return ExternalOperationSnapshot(
                    component=component,
                    operation=operation,
                    success_recent=95,
                    failure_recent=5,
                    attempts_recent=100,
                    failure_rate_percent=5.0,
                )
            return ExternalOperationSnapshot(
                component=component,
                operation=operation,
                success_recent=48,
                failure_recent=2,
                attempts_recent=50,
                failure_rate_percent=4.0,
            )

        service = PlatformRuntimeMetricsService(
            settings=settings,
            redis_info_provider=redis_info_provider,
            broker_lag_provider=broker_lag_provider,
            pgbouncer_stats_provider=pgbouncer_stats_provider,
            clickhouse_ping_provider=clickhouse_ping_provider,
            object_storage_ping_provider=object_storage_ping_provider,
            operation_snapshot_provider=operation_snapshot_provider,
        )

        metrics = await service.collect_metric_points()

        metric_index = {
            (metric.name, tuple(sorted(metric.labels.items()))): metric.value for metric in metrics
        }
        self.assertEqual(metric_index[("redis_available", ())], 1.0)
        self.assertEqual(metric_index[("redis_used_memory_bytes", ())], 512.0)
        self.assertEqual(metric_index[("redis_memory_utilization_percent", ())], 50.0)
        self.assertEqual(
            metric_index[
                (
                    "event_broker_consumer_lag_total",
                    (("backend", "kafka"), ("group", "stock-py.dispatchers")),
                )
            ],
            27.0,
        )
        self.assertEqual(
            metric_index[("pgbouncer_clients_waiting", (("database", "stock_py"),))],
            2.0,
        )
        self.assertEqual(metric_index[("clickhouse_available", ())], 1.0)
        self.assertEqual(metric_index[("object_storage_available", ())], 1.0)
        self.assertEqual(
            metric_index[
                (
                    "clickhouse_write_failure_rate_percent",
                    (("window_minutes", "15"),),
                )
            ],
            5.0,
        )
        self.assertEqual(
            metric_index[
                (
                    "object_storage_archive_window_failures_total",
                    (("window_minutes", "15"),),
                )
            ],
            2.0,
        )

    async def test_collect_alerts_surfaces_capacity_and_error_conditions(self) -> None:
        settings = Settings(
            database_url="postgresql+asyncpg://stock_py:stock_py@pgbouncer:6432/stock_py",
            database_pool_mode="pgbouncer",
            pgbouncer_admin_url="postgresql://stock_py:stock_py@pgbouncer:6432/pgbouncer",
            analytics_backend="clickhouse",
            object_storage_backend="s3",
            runtime_alert_broker_lag_threshold=100,
            runtime_alert_pgbouncer_waiting_clients_threshold=5,
            runtime_alert_redis_memory_percent_threshold=80,
            runtime_alert_clickhouse_write_failure_rate_threshold=5,
            runtime_alert_object_storage_archive_failure_rate_threshold=5,
        )

        async def redis_info_provider() -> dict[str, object]:
            return {"used_memory": 900, "maxmemory": 1000, "evicted_keys": 0}

        async def broker_lag_provider() -> dict[str, object]:
            return {
                "available": True,
                "backend": "kafka",
                "group_name": "stock-py.dispatchers",
                "lag_total": 250,
                "max_partition_lag": 120,
                "partitions": 3,
            }

        async def pgbouncer_stats_provider(_admin_dsn: str) -> dict[str, object]:
            return {
                "available": True,
                "database": "stock_py",
                "cl_active": 12,
                "cl_waiting": 7,
                "sv_active": 5,
                "sv_idle": 4,
            }

        async def clickhouse_ping_provider() -> dict[str, object]:
            raise RuntimeError("clickhouse unavailable")

        async def object_storage_ping_provider() -> dict[str, object]:
            return {"backend": "s3", "bucket": "stock-py"}

        async def operation_snapshot_provider(
            component: str,
            operation: str,
            *,
            window_seconds: int,
        ) -> ExternalOperationSnapshot:
            del operation, window_seconds
            if component == "clickhouse":
                return ExternalOperationSnapshot(
                    component=component,
                    operation="insert_rows",
                    success_recent=19,
                    failure_recent=1,
                    attempts_recent=20,
                    failure_rate_percent=5.0,
                )
            return ExternalOperationSnapshot(
                component=component,
                operation="put_bytes",
                success_recent=8,
                failure_recent=2,
                attempts_recent=10,
                failure_rate_percent=20.0,
            )

        service = PlatformRuntimeMetricsService(
            settings=settings,
            redis_info_provider=redis_info_provider,
            broker_lag_provider=broker_lag_provider,
            pgbouncer_stats_provider=pgbouncer_stats_provider,
            clickhouse_ping_provider=clickhouse_ping_provider,
            object_storage_ping_provider=object_storage_ping_provider,
            operation_snapshot_provider=operation_snapshot_provider,
        )

        alerts = await service.collect_alerts()

        summary_index = {(alert.component, alert.summary): alert for alert in alerts}
        self.assertIn(("event-broker", "Broker consumer lag exceeded threshold"), summary_index)
        self.assertIn(("pgbouncer", "PgBouncer waiting clients exceeded threshold"), summary_index)
        self.assertIn(("redis", "Redis memory usage exceeded threshold"), summary_index)
        self.assertIn(
            ("clickhouse", "ClickHouse write failure rate exceeded threshold"), summary_index
        )
        self.assertIn(
            (
                "object-storage-archive",
                "Object storage archive failure rate exceeded threshold",
            ),
            summary_index,
        )
        clickhouse_probe = next(
            alert
            for alert in alerts
            if alert.component == "clickhouse" and "readiness probe failed" in alert.summary
        )
        self.assertEqual(clickhouse_probe.severity, "critical")


if __name__ == "__main__":
    unittest.main()
