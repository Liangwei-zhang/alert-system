import unittest

from infra.observability.metrics import MetricsRegistry


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


if __name__ == "__main__":
    unittest.main()
