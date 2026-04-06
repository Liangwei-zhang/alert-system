import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from apps.admin_api import main as admin_main
from apps.admin_api.routers.runtime_monitoring import (
    RuntimeMetricPointResponse,
    RuntimeMetricsResponse,
)
from infra.security.auth import require_admin


class AdminMetricsEndpointTest(unittest.TestCase):
    def setUp(self) -> None:
        admin_main.metrics.reset()

        async def override_db_session():
            yield object()

        admin_main.app.dependency_overrides[admin_main.get_db_session] = override_db_session
        admin_main.app.dependency_overrides[require_admin] = lambda: {"sub": "unit-test"}
        self.client = TestClient(admin_main.app)

    def tearDown(self) -> None:
        self.client.close()
        admin_main.app.dependency_overrides.clear()
        admin_main.metrics.reset()

    def test_metrics_endpoint_exports_runtime_metrics_in_prometheus_format(self) -> None:
        admin_main.metrics.counter("admin_http_requests_total", "Total admin API requests").inc(3)

        runtime_payload = RuntimeMetricsResponse(
            recorded_at="2026-04-06T05:00:00Z",
            metrics=[
                RuntimeMetricPointResponse(
                    name="event_broker_consumer_lag_total",
                    value=18.0,
                    labels={"backend": "kafka", "group": "stock-py.dispatchers"},
                ),
                RuntimeMetricPointResponse(
                    name="runtime_coverage_percent",
                    value=100.0,
                ),
            ],
        )

        with patch.object(
            admin_main,
            "collect_runtime_metrics_payload",
            AsyncMock(return_value=runtime_payload),
        ) as collect_metrics:
            response = self.client.get("/metrics", params={"format": "prometheus"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("stock_signal_admin_admin_http_requests_total 3.0", response.text)
        self.assertIn(
            'stock_signal_admin_event_broker_consumer_lag_total{backend="kafka",group="stock-py.dispatchers"} 18.0',
            response.text,
        )
        self.assertIn("stock_signal_admin_runtime_coverage_percent 100.0", response.text)
        collect_metrics.assert_awaited_once()
        self.assertIsNone(collect_metrics.await_args.kwargs["component_kind"])


if __name__ == "__main__":
    unittest.main()