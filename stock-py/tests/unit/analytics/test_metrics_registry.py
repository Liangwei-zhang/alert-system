import unittest

from infra.observability.metrics import (
    MetricsRegistry,
    PrometheusMetricSample,
    get_http_request_tracker,
    prometheus_samples_text,
)


class MetricsRegistryTest(unittest.TestCase):
    def test_histogram_snapshot_tracks_aggregate_values_without_exposing_samples(self) -> None:
        registry = MetricsRegistry()
        histogram = registry.histogram("request_latency_ms", "Request latency")

        for value in (12.5, 7.5, 18.0):
            histogram.observe(value)

        snapshot = histogram.snapshot()

        self.assertEqual(snapshot["type"], "histogram")
        self.assertEqual(snapshot["description"], "Request latency")
        self.assertEqual(snapshot["count"], 3)
        self.assertEqual(snapshot["sum"], 38.0)
        self.assertEqual(snapshot["min"], 7.5)
        self.assertEqual(snapshot["max"], 18.0)
        self.assertEqual(snapshot["p50"], 12.5)
        self.assertEqual(snapshot["p95"], 18.0)
        self.assertEqual(snapshot["p99"], 18.0)

    def test_prometheus_export_and_reset(self) -> None:
        registry = MetricsRegistry()
        registry.counter("http_requests_total", "Total requests").inc(3)
        registry.gauge("queue_depth", "Queue depth").set(7)
        registry.histogram("request_latency_ms", "Request latency").observe(12.5)

        payload = registry.prometheus_text("stock_signal")

        self.assertIn("stock_signal_http_requests_total 3.0", payload)
        self.assertIn("stock_signal_queue_depth 7", payload)
        self.assertIn("stock_signal_request_latency_ms_p95 12.5", payload)

        registry.reset()
        self.assertEqual(registry.snapshot(), {})

    def test_http_request_tracker_snapshot_and_prometheus_export(self) -> None:
        tracker = get_http_request_tracker("unit-test-service")
        tracker.reset()
        tracker.record(method="GET", path="/health", status_code=200, duration_ms=4.0)
        tracker.record(method="POST", path="/v1/trades", status_code=503, duration_ms=18.0)

        snapshot = tracker.snapshot()

        self.assertEqual(snapshot["requests"], 2)
        self.assertEqual(snapshot["errors"], 1)
        self.assertIn("GET /health", snapshot["endpoints"])
        self.assertEqual(snapshot["endpoints"]["POST /v1/trades"]["errors"], 1)

        payload = tracker.prometheus_text("stock_signal")
        self.assertIn(
            'stock_signal_endpoint_requests_total{service="unit-test-service",method="GET",path="/health"} 1',
            payload,
        )
        self.assertIn(
            'stock_signal_endpoint_errors_total{service="unit-test-service",method="POST",path="/v1/trades"} 1',
            payload,
        )

    def test_prometheus_samples_text_renders_labeled_runtime_gauges(self) -> None:
        payload = prometheus_samples_text(
            [
                PrometheusMetricSample(
                    name="event_broker_consumer_lag_total",
                    value=12.0,
                    labels={"backend": "kafka", "group": "stock-py.dispatchers"},
                ),
                PrometheusMetricSample(
                    name="runtime_coverage_percent",
                    value=100.0,
                ),
            ],
            "stock_signal_admin",
        )

        self.assertIn(
            "# TYPE stock_signal_admin_event_broker_consumer_lag_total gauge",
            payload,
        )
        self.assertIn(
            'stock_signal_admin_event_broker_consumer_lag_total{backend="kafka",group="stock-py.dispatchers"} 12.0',
            payload,
        )
        self.assertIn("stock_signal_admin_runtime_coverage_percent 100.0", payload)


if __name__ == "__main__":
    unittest.main()
