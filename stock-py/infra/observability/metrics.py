from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from time import time
from typing import Any


def _escape_prometheus_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_prometheus_labels(labels: dict[str, str]) -> str:
    if not labels:
        return ""
    pairs = [f'{key}="{_escape_prometheus_label(labels[key])}"' for key in sorted(labels)]
    return "{" + ",".join(pairs) + "}"


def _sanitize_prometheus_metric_name(name: str) -> str:
    sanitized = []
    for char in name:
        if char.isalnum() or char in {"_", ":"}:
            sanitized.append(char)
        else:
            sanitized.append("_")
    return "".join(sanitized)


@dataclass
class CounterMetric:
    name: str
    description: str = ""
    value: float = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def snapshot(self) -> dict[str, Any]:
        return {"type": "counter", "description": self.description, "value": self.value}


@dataclass
class GaugeMetric:
    name: str
    description: str = ""
    value: float = 0.0

    def set(self, value: float) -> None:
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        self.value -= amount

    def snapshot(self) -> dict[str, Any]:
        return {"type": "gauge", "description": self.description, "value": self.value}


@dataclass
class HistogramMetric:
    name: str
    description: str = ""
    count: int = 0
    total: float = 0.0
    min_value: float | None = None
    max_value: float | None = None
    samples: deque[float] = field(default_factory=lambda: deque(maxlen=2048), repr=False)

    @staticmethod
    def _percentile(values: list[float], percentile: int) -> float | None:
        if not values:
            return None
        ordered = sorted(values)
        rank = max(0, ((percentile * len(ordered)) + 99) // 100 - 1)
        return ordered[min(rank, len(ordered) - 1)]

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.samples.append(value)
        if self.min_value is None or value < self.min_value:
            self.min_value = value
        if self.max_value is None or value > self.max_value:
            self.max_value = value

    def snapshot(self) -> dict[str, Any]:
        if self.count == 0:
            return {
                "type": "histogram",
                "description": self.description,
                "count": 0,
                "sum": 0.0,
                "min": None,
                "max": None,
                "p50": None,
                "p95": None,
                "p99": None,
            }

        values = list(self.samples)

        return {
            "type": "histogram",
            "description": self.description,
            "count": self.count,
            "sum": self.total,
            "min": self.min_value,
            "max": self.max_value,
            "p50": self._percentile(values, 50),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99),
        }


@dataclass(frozen=True, slots=True)
class PrometheusMetricSample:
    name: str
    value: float
    description: str = ""
    metric_type: str = "gauge"
    labels: dict[str, str] = field(default_factory=dict)


def prometheus_samples_text(
    samples: list[PrometheusMetricSample],
    prefix: str = "stock_signal",
) -> str:
    metric_families: dict[str, dict[str, Any]] = {}
    ordered_samples = sorted(
        samples,
        key=lambda sample: (
            _sanitize_prometheus_metric_name(sample.name),
            tuple(sorted(sample.labels.items())),
        ),
    )

    for sample in ordered_samples:
        metric_name = f"{prefix}_{_sanitize_prometheus_metric_name(sample.name)}"
        family = metric_families.setdefault(
            metric_name,
            {
                "description": sample.description or sample.name,
                "metric_type": sample.metric_type,
                "samples": [],
            },
        )
        family["samples"].append(sample)

    lines: list[str] = []
    for metric_name in sorted(metric_families):
        family = metric_families[metric_name]
        lines.append(f"# HELP {metric_name} {family['description']}")
        lines.append(f"# TYPE {metric_name} {family['metric_type']}")
        for sample in family["samples"]:
            lines.append(
                f"{metric_name}{_format_prometheus_labels(sample.labels)} {sample.value}"
            )

    return "\n".join(lines) + ("\n" if lines else "")


@dataclass
class HttpEndpointMetric:
    method: str
    path: str
    requests: int = 0
    errors: int = 0
    last_status_code: int | None = None
    latency: HistogramMetric = field(
        default_factory=lambda: HistogramMetric(name="latency_ms")
    )

    def record(self, *, status_code: int, duration_ms: float) -> None:
        self.requests += 1
        if status_code >= 500:
            self.errors += 1
        self.last_status_code = status_code
        self.latency.observe(duration_ms)

    def snapshot(self) -> dict[str, Any]:
        latency = self.latency.snapshot()
        return {
            "method": self.method,
            "path": self.path,
            "requests": self.requests,
            "errors": self.errors,
            "last_status_code": self.last_status_code,
            "p50_latency_ms": latency["p50"],
            "p95_latency_ms": latency["p95"],
            "p99_latency_ms": latency["p99"],
        }


class HttpRequestTracker:
    def __init__(self, service_name: str) -> None:
        self.service_name = service_name
        self._started_at = time()
        self._endpoints: dict[tuple[str, str], HttpEndpointMetric] = {}

    def uptime_seconds(self) -> float:
        return max(time() - self._started_at, 0.0)

    def reset(self) -> None:
        self._endpoints = {}
        self._started_at = time()

    def record(self, *, method: str, path: str, status_code: int, duration_ms: float) -> None:
        key = (method.upper(), path)
        if key not in self._endpoints:
            self._endpoints[key] = HttpEndpointMetric(method=key[0], path=key[1])
        self._endpoints[key].record(status_code=status_code, duration_ms=duration_ms)

    def snapshot(self) -> dict[str, Any]:
        endpoint_payload: dict[str, Any] = {}
        total_requests = 0
        total_errors = 0

        for endpoint in self._endpoints.values():
            key = f"{endpoint.method} {endpoint.path}"
            endpoint_payload[key] = endpoint.snapshot()
            total_requests += endpoint.requests
            total_errors += endpoint.errors

        return {
            "requests": total_requests,
            "errors": total_errors,
            "uptime_seconds": round(self.uptime_seconds(), 3),
            "endpoints": endpoint_payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def prometheus_text(self, prefix: str = "stock_signal") -> str:
        snapshot = self.snapshot()
        lines = [
            f'# HELP {prefix}_endpoint_requests_total Total requests recorded by the HTTP request tracker.',
            f'# TYPE {prefix}_endpoint_requests_total counter',
            f'# HELP {prefix}_endpoint_errors_total Total 5xx responses recorded by the HTTP request tracker.',
            f'# TYPE {prefix}_endpoint_errors_total counter',
            f'# HELP {prefix}_endpoint_latency_ms_p95 P95 latency in milliseconds for tracked HTTP endpoints.',
            f'# TYPE {prefix}_endpoint_latency_ms_p95 gauge',
            f'# HELP {prefix}_endpoint_latency_ms_p99 P99 latency in milliseconds for tracked HTTP endpoints.',
            f'# TYPE {prefix}_endpoint_latency_ms_p99 gauge',
            f'# HELP {prefix}_endpoint_uptime_seconds Uptime of the tracked HTTP service in seconds.',
            f'# TYPE {prefix}_endpoint_uptime_seconds gauge',
            (
                f'{prefix}_endpoint_uptime_seconds{{service="{_escape_prometheus_label(self.service_name)}"}} '
                f'{snapshot["uptime_seconds"]}'
            ),
        ]
        for endpoint in self._endpoints.values():
            labels = (
                f'service="{_escape_prometheus_label(self.service_name)}",'
                f'method="{_escape_prometheus_label(endpoint.method)}",'
                f'path="{_escape_prometheus_label(endpoint.path)}"'
            )
            latency = endpoint.latency.snapshot()
            lines.append(
                f"{prefix}_endpoint_requests_total{{{labels}}} {endpoint.requests}"
            )
            lines.append(f"{prefix}_endpoint_errors_total{{{labels}}} {endpoint.errors}")
            if latency["p95"] is not None:
                lines.append(f"{prefix}_endpoint_latency_ms_p95{{{labels}}} {latency['p95']}")
            if latency["p99"] is not None:
                lines.append(f"{prefix}_endpoint_latency_ms_p99{{{labels}}} {latency['p99']}")
        return "\n".join(lines) + "\n"


class MetricsRegistry:
    def __init__(self) -> None:
        self._started_at = time()
        self._counters: dict[str, CounterMetric] = {}
        self._gauges: dict[str, GaugeMetric] = {}
        self._histograms: dict[str, HistogramMetric] = {}

    def counter(self, name: str, description: str = "") -> CounterMetric:
        if name not in self._counters:
            self._counters[name] = CounterMetric(name=name, description=description)
        return self._counters[name]

    def histogram(self, name: str, description: str = "") -> HistogramMetric:
        if name not in self._histograms:
            self._histograms[name] = HistogramMetric(name=name, description=description)
        return self._histograms[name]

    def gauge(self, name: str, description: str = "") -> GaugeMetric:
        if name not in self._gauges:
            self._gauges[name] = GaugeMetric(name=name, description=description)
        return self._gauges[name]

    def uptime_seconds(self) -> float:
        return max(time() - self._started_at, 0.0)

    def reset(self) -> None:
        self._counters = {}
        self._gauges = {}
        self._histograms = {}
        self._started_at = time()

    def snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for name, metric in self._counters.items():
            snapshot[name] = metric.snapshot()
        for name, metric in self._gauges.items():
            snapshot[name] = metric.snapshot()
        for name, metric in self._histograms.items():
            snapshot[name] = metric.snapshot()
        return snapshot

    @staticmethod
    def _sanitize_metric_name(name: str) -> str:
        return _sanitize_prometheus_metric_name(name)

    def prometheus_text(self, prefix: str = "stock_signal") -> str:
        lines = [
            f'# HELP {prefix}_uptime_seconds Process uptime in seconds since the metrics registry was last reset.',
            f'# TYPE {prefix}_uptime_seconds gauge',
            f"{prefix}_uptime_seconds {round(self.uptime_seconds(), 3)}",
        ]

        for name, metric in sorted(self._counters.items()):
            metric_name = f"{prefix}_{self._sanitize_metric_name(name)}"
            lines.extend(
                [
                    f"# HELP {metric_name} {metric.description or metric.name}",
                    f"# TYPE {metric_name} counter",
                    f"{metric_name} {metric.value}",
                ]
            )

        for name, metric in sorted(self._gauges.items()):
            metric_name = f"{prefix}_{self._sanitize_metric_name(name)}"
            lines.extend(
                [
                    f"# HELP {metric_name} {metric.description or metric.name}",
                    f"# TYPE {metric_name} gauge",
                    f"{metric_name} {metric.value}",
                ]
            )

        for name, metric in sorted(self._histograms.items()):
            metric_name = f"{prefix}_{self._sanitize_metric_name(name)}"
            snapshot = metric.snapshot()
            lines.extend(
                [
                    f"# HELP {metric_name} {metric.description or metric.name}",
                    f"# TYPE {metric_name} summary",
                    f"{metric_name}_count {snapshot['count']}",
                    f"{metric_name}_sum {snapshot['sum']}",
                ]
            )
            if snapshot["min"] is not None:
                lines.append(f"{metric_name}_min {snapshot['min']}")
            if snapshot["max"] is not None:
                lines.append(f"{metric_name}_max {snapshot['max']}")
            if snapshot["p50"] is not None:
                lines.append(f"{metric_name}_p50 {snapshot['p50']}")
            if snapshot["p95"] is not None:
                lines.append(f"{metric_name}_p95 {snapshot['p95']}")
            if snapshot["p99"] is not None:
                lines.append(f"{metric_name}_p99 {snapshot['p99']}")

        return "\n".join(lines) + "\n"


@lru_cache(maxsize=1)
def get_metrics_registry() -> MetricsRegistry:
    return MetricsRegistry()


@lru_cache(maxsize=None)
def get_http_request_tracker(service_name: str = "default") -> HttpRequestTracker:
    return HttpRequestTracker(service_name)
