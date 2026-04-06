"""
Performance benchmarks for key operations.

Run with: pytest tests/benchmark/ -v --benchmark-only
Install: pip install pytest-benchmark
"""
import time
import numpy as np
import pytest

from domains.signals.advanced_algorithms import (
    AdvancedSignalGenerator,
    MarketRegimeDetector,
    MultiTimeframeAnalyzer,
    PatternRecognizer,
    TrendStrengthCalculator,
    VolumeProfileAnalyzer,
)


def generate_test_data(num_points: int = 100):
    """Generate test data for benchmarks."""
    base = 100.0
    close = [base + np.random.randn() * base * 0.01 for _ in range(num_points)]
    high = [c * 1.02 for c in close]
    low = [c * 0.98 for c in close]
    volume = list(np.random.randint(1000, 100000, num_points))
    return close, high, low, volume


class BenchmarkSignalAlgorithms:
    """Benchmarks for signal algorithm performance."""

    @pytest.fixture
    def small_data(self):
        """Small dataset (30 points)."""
        return generate_test_data(30)

    @pytest.fixture
    def medium_data(self):
        """Medium dataset (100 points)."""
        return generate_test_data(100)

    @pytest.fixture
    def large_data(self):
        """Large dataset (500 points)."""
        return generate_test_data(500)

    def test_trend_strength_small(self, benchmark, small_data):
        """Benchmark trend strength with small data."""
        close, high, low, volume = small_data
        result = benchmark(TrendStrengthCalculator.calculate, close, high, low, volume)
        assert "strength" in result

    def test_trend_strength_medium(self, benchmark, medium_data):
        """Benchmark trend strength with medium data."""
        close, high, low, volume = medium_data
        result = benchmark(TrendStrengthCalculator.calculate, close, high, low, volume)
        assert "strength" in result

    def test_trend_strength_large(self, benchmark, large_data):
        """Benchmark trend strength with large data."""
        close, high, low, volume = large_data
        result = benchmark(TrendStrengthCalculator.calculate, close, high, low, volume)
        assert "strength" in result

    def test_volume_profile_small(self, benchmark, small_data):
        """Benchmark volume profile with small data."""
        close, high, low, volume = small_data
        result = benchmark(VolumeProfileAnalyzer.analyze, close, high, low, volume)
        assert "vwap" in result

    def test_volume_profile_medium(self, benchmark, medium_data):
        """Benchmark volume profile with medium data."""
        close, high, low, volume = medium_data
        result = benchmark(VolumeProfileAnalyzer.analyze, close, high, low, volume)
        assert "vwap" in result

    def test_pattern_recognizer_small(self, benchmark, small_data):
        """Benchmark pattern recognizer with small data."""
        close, high, low, volume = small_data
        result = benchmark(PatternRecognizer.recognize, close, high, low, volume)
        assert "patterns" in result

    def test_pattern_recognizer_medium(self, benchmark, medium_data):
        """Benchmark pattern recognizer with medium data."""
        close, high, low, volume = medium_data
        result = benchmark(PatternRecognizer.recognize, close, high, low, volume)
        assert "patterns" in result

    def test_market_regime_small(self, benchmark, small_data):
        """Benchmark market regime with small data."""
        close, high, low, volume = small_data
        result = benchmark(MarketRegimeDetector.detect, close, high, low, volume)
        assert "regime" in result

    def test_market_regime_medium(self, benchmark, medium_data):
        """Benchmark market regime with medium data."""
        close, high, low, volume = medium_data
        result = benchmark(MarketRegimeDetector.detect, close, high, low, volume)
        assert "regime" in result

    def test_multi_tf_analyzer(self, benchmark):
        """Benchmark multi-timeframe analyzer."""
        data = {
            "1h": {"close": generate_test_data(50)[0]},
            "4h": {"close": generate_test_data(50)[0]},
            "1d": {"close": generate_test_data(50)[0]},
        }
        analyzer = MultiTimeframeAnalyzer()
        result = benchmark(analyzer.analyze, data)
        assert "confirm" in result

    def test_signal_generator_medium(self, benchmark, medium_data):
        """Benchmark full signal generation."""
        generator = AdvancedSignalGenerator()
        data = {
            "close": medium_data[0],
            "high": medium_data[1],
            "low": medium_data[2],
            "volume": medium_data[3],
        }
        result = benchmark(generator.generate, data)
        # Result can be None or valid signal


class BenchmarkBatchOperations:
    """Benchmarks for batch processing performance."""

    def test_batch_trend_strength_100_calls(self, benchmark):
        """Benchmark 100 trend strength calculations."""
        def run_batch():
            for _ in range(100):
                close, high, low, volume = generate_test_data(30)
                TrendStrengthCalculator.calculate(close, high, low, volume)
        
        benchmark(run_batch)

    def test_batch_volume_profile_100_calls(self, benchmark):
        """Benchmark 100 volume profile calculations."""
        def run_batch():
            for _ in range(100):
                close, high, low, volume = generate_test_data(30)
                VolumeProfileAnalyzer.analyze(close, high, low, volume)
        
        benchmark(run_batch)

    def test_batch_pattern_recognition_100_calls(self, benchmark):
        """Benchmark 100 pattern recognition calls."""
        def run_batch():
            for _ in range(100):
                close, high, low, volume = generate_test_data(30)
                PatternRecognizer.recognize(close, high, low, volume)
        
        benchmark(run_batch)


class BenchmarkThroughput:
    """Throughput benchmarks."""

    @pytest.fixture
    def throughput_data(self):
        """Data for throughput test."""
        return generate_test_data(50)

    def test_signals_per_second(self, benchmark, throughput_data):
        """Measure signals processed per second."""
        close, high, low, volume = throughput_data
        generator = AdvancedSignalGenerator()
        
        def generate_signals():
            count = 0
            start = time.time()
            while time.time() - start < 1.0:  # Run for 1 second
                generator.generate({"close": close, "high": high, "low": low, "volume": volume})
                count += 1
            return count
        
        signals_per_sec = benchmark(generate_signals)
        # Expect at least 10 signals per second
        assert signals_per_sec >= 10

    def test_calculations_per_second(self, benchmark, throughput_data):
        """Measure trend calculations per second."""
        close, high, low, volume = throughput_data
        
        def calculate_trend():
            count = 0
            start = time.time()
            while time.time() - start < 1.0:
                TrendStrengthCalculator.calculate(close, high, low, volume)
                count += 1
            return count
        
        calcs_per_sec = benchmark(calculate_trend)
        # Expect at least 50 calculations per second
        assert calcs_per_sec >= 50
