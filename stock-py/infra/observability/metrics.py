from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any


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

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
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
            }

        return {
            "type": "histogram",
            "description": self.description,
            "count": self.count,
            "sum": self.total,
            "min": self.min_value,
            "max": self.max_value,
        }


class MetricsRegistry:
    def __init__(self) -> None:
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

    def snapshot(self) -> dict[str, Any]:
        snapshot: dict[str, Any] = {}
        for name, metric in self._counters.items():
            snapshot[name] = metric.snapshot()
        for name, metric in self._gauges.items():
            snapshot[name] = metric.snapshot()
        for name, metric in self._histograms.items():
            snapshot[name] = metric.snapshot()
        return snapshot


@lru_cache(maxsize=1)
def get_metrics_registry() -> MetricsRegistry:
    return MetricsRegistry()
