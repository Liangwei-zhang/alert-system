from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.public_api.routers import monitoring as monitoring_router
from infra.core.errors import register_exception_handlers
from infra.observability.metrics import get_http_request_tracker, get_metrics_registry


class MonitoringRouterIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            debug=False,
            environment="staging",
            internal_sidecar_secret="secret-token",
            internal_signal_ingest_secret="",
        )
        self.settings_patch = patch.object(
            monitoring_router,
            "get_settings",
            lambda: self.settings,
        )
        self.settings_patch.start()

        self.metrics = get_metrics_registry()
        self.metrics.reset()
        self.tracker = get_http_request_tracker("public-api")
        self.tracker.reset()

        self.app = FastAPI()
        register_exception_handlers(self.app)
        self.app.include_router(monitoring_router.router)
        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.client.close()
        self.metrics.reset()
        self.tracker.reset()
        self.settings_patch.stop()

    def test_stats_and_metrics_routes_require_internal_secret(self) -> None:
        self.metrics.counter("http_requests_total", "Total requests").inc(2)
        self.metrics.counter("http_request_errors_total", "Total errors").inc()
        self.metrics.histogram("http_request_duration_ms", "Latency").observe(11.0)
        self.metrics.histogram("http_request_duration_ms", "Latency").observe(37.0)
        self.tracker.record(
            method="GET",
            path="/v1/account/profile",
            status_code=200,
            duration_ms=11.0,
        )
        self.tracker.record(
            method="POST",
            path="/v1/trades/confirm",
            status_code=503,
            duration_ms=37.0,
        )

        forbidden = self.client.get("/api/monitoring/stats")
        self.assertEqual(forbidden.status_code, 403)

        stats_response = self.client.get(
            "/api/monitoring/stats",
            headers={"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(stats_response.status_code, 200)
        payload = stats_response.json()
        self.assertEqual(payload["requests"], 2)
        self.assertEqual(payload["errors"], 1)
        self.assertEqual(
            payload["endpoints"]["GET /v1/account/profile"],
            {
                "method": "GET",
                "path": "/v1/account/profile",
                "requests": 1,
                "errors": 0,
                "last_status_code": 200,
                "p50_latency_ms": 11.0,
                "p95_latency_ms": 11.0,
                "p99_latency_ms": 11.0,
            },
        )
        self.assertEqual(payload["endpoints"]["POST /v1/trades/confirm"]["errors"], 1)

        metrics_response = self.client.get(
            "/api/monitoring/metrics",
            headers={"X-Internal-Sidecar-Secret": "secret-token"},
        )
        self.assertEqual(metrics_response.status_code, 200)
        self.assertIn("stock_signal_http_requests_total 2.0", metrics_response.text)
        self.assertIn(
            'stock_signal_endpoint_requests_total{service="public-api",method="GET",path="/v1/account/profile"} 1',
            metrics_response.text,
        )

    def test_reset_is_blocked_in_production_and_available_elsewhere(self) -> None:
        self.metrics.counter("http_requests_total", "Total requests").inc()
        self.tracker.record(method="GET", path="/health", status_code=200, duration_ms=5.0)

        self.settings.environment = "production"
        blocked = self.client.post(
            "/api/monitoring/reset",
            headers={"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(blocked.status_code, 403)

        self.settings.environment = "staging"
        allowed = self.client.post(
            "/api/monitoring/reset",
            headers={"Authorization": "Bearer secret-token"},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.json(), {"ok": True, "message": "Metrics reset complete"})
        self.assertEqual(self.metrics.snapshot(), {})
        self.assertEqual(self.tracker.snapshot()["requests"], 0)


if __name__ == "__main__":
    unittest.main()