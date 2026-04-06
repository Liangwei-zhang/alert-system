"""Metrics registry for observability."""
from typing import Dict, Callable, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import time


class MetricType(Enum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"


@dataclass
class Metric:
    """Base metric definition."""
    
    name: str
    description: str
    metric_type: MetricType
    labels: Dict[str, str] = field(default_factory=dict)
    value: float = 0.0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Counter(Metric):
    """Counter metric."""
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None):
        super().__init__(
            name=name,
            description=description,
            metric_type=MetricType.COUNTER,
            labels=labels or {},
        )
    
    def increment(self, value: float = 1.0) -> None:
        self.value += value
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class Histogram(Metric):
    """Histogram metric."""
    
    buckets: Dict[str, float] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None, buckets: Dict[str, float] = None):
        super().__init__(
            name=name,
            description=description,
            metric_type=MetricType.HISTOGRAM,
            labels=labels or {},
        )
        self.buckets = buckets or {}
        self.sum = 0.0
        self.count = 0
    
    def observe(self, value: float) -> None:
        self.value = value
        self.sum += value
        self.count += 1
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class Gauge(Metric):
    """Gauge metric."""
    
    def __init__(self, name: str, description: str = "", labels: Dict[str, str] = None):
        super().__init__(
            name=name,
            description=description,
            metric_type=MetricType.GAUGE,
            labels=labels or {},
        )
    
    def set(self, value: float) -> None:
        self.value = value
        self.last_updated = datetime.now(timezone.utc)
    
    def increment(self, value: float = 1.0) -> None:
        self.value += value
        self.last_updated = datetime.now(timezone.utc)
    
    def decrement(self, value: float = 1.0) -> None:
        self.value -= value
        self.last_updated = datetime.now(timezone.utc)


class MetricsRegistry:
    """Registry for managing application metrics."""
    
    def __init__(self):
        self._counters: Dict[str, Counter] = {}
        self._histograms: Dict[str, Histogram] = {}
        self._gauges: Dict[str, Gauge] = {}
    
    def counter(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> Counter:
        """Get or create a counter metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels
            
        Returns:
            Counter metric
        """
        key = self._make_key(name, labels)
        if key not in self._counters:
            self._counters[key] = Counter(name, description, labels)
        return self._counters[key]
    
    def histogram(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
        buckets: Optional[Dict[str, float]] = None,
    ) -> Histogram:
        """Get or create a histogram metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels
            buckets: Optional histogram buckets
            
        Returns:
            Histogram metric
        """
        key = self._make_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = Histogram(name, description, labels, buckets)
        return self._histograms[key]
    
    def gauge(
        self,
        name: str,
        description: str = "",
        labels: Optional[Dict[str, str]] = None,
    ) -> Gauge:
        """Get or create a gauge metric.
        
        Args:
            name: Metric name
            description: Metric description
            labels: Optional labels
            
        Returns:
            Gauge metric
        """
        key = self._make_key(name, labels)
        if key not in self._gauges:
            self._gauges[key] = Gauge(name, description, labels)
        return self._gauges[key]
    
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all registered metrics."""
        return {
            "counters": {k: {"value": v.value, "labels": v.labels} for k, v in self._counters.items()},
            "histograms": {k: {"value": v.value, "count": v.count, "sum": v.sum, "labels": v.labels} for k, v in self._histograms.items()},
            "gauges": {k: {"value": v.value, "labels": v.labels} for k, v in self._gauges.items()},
        }
    
    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._histograms.clear()
        self._gauges.clear()
    
    def _make_key(self, name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a unique key for a metric."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global registry instance
_global_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """Get the global metrics registry."""
    global _global_registry
    if _global_registry is None:
        _global_registry = MetricsRegistry()
    return _global_registry