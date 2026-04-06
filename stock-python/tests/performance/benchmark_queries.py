"""Basic query benchmarks for database performance testing."""
import asyncio
import time
import statistics
from typing import List, Dict, Any, Callable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager


@dataclass
class BenchmarkResult:
    """Result of a benchmark run."""
    name: str
    iterations: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    std_dev: float = 0.0
    times: List[float] = field(default_factory=list)
    
    def __post_init__(self):
        if self.times:
            self.std_dev = statistics.stdev(self.times) if len(self.times) > 1 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "iterations": self.iterations,
            "total_time": self.total_time,
            "avg_time": self.avg_time,
            "min_time": self.min_time,
            "max_time": self.max_time,
            "std_dev": self.std_dev,
        }


class QueryBenchmark:
    """Benchmark harness for database queries."""
    
    def __init__(self, name: str, iterations: int = 100):
        self.name = name
        self.iterations = iterations
        self.results: List[BenchmarkResult] = []
    
    async def run(
        self,
        query_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Run a benchmark for a query function."""
        times: List[float] = []
        
        for _ in range(self.iterations):
            start = time.perf_counter()
            await query_fn(*args, **kwargs)
            end = time.perf_counter()
            times.append(end - start)
        
        result = BenchmarkResult(
            name=self.name,
            iterations=self.iterations,
            total_time=sum(times),
            avg_time=statistics.mean(times),
            min_time=min(times),
            max_time=max(times),
            times=times,
        )
        
        self.results.append(result)
        return result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all benchmark results."""
        return {
            "benchmarks": [r.to_dict() for r in self.results],
            "fastest": min(self.results, key=lambda r: r.avg_time).name if self.results else None,
            "slowest": max(self.results, key=lambda r: r.avg_time).name if self.results else None,
        }


async def benchmark_queries(db_session: Any) -> Dict[str, Any]:
    """Run benchmarks for common database queries.
    
    This is a template showing how to benchmark queries.
    Adjust based on actual models and queries.
    """
    benchmark = QueryBenchmark("database_queries", iterations=50)
    
    # Example benchmarks - adjust to match actual models
    # Uncomment and modify for actual use:
    
    # from sqlalchemy import select
    # from infra.db.models import MarketData, System
    # from infra.db.repository_base import BaseRepository
    # 
    # async def benchmark_market_data_fetch():
    #     """Benchmark: Fetch all market data."""
    #     from sqlalchemy import select
    #     stmt = select(MarketData)
    #     await db_session.execute(stmt)
    # 
    # async def benchmark_market_data_by_symbol():
    #     """Benchmark: Fetch market data by symbol."""
    #     stmt = select(MarketData).where(MarketData.symbol == "AAPL")
    #     await db_session.execute(stmt)
    # 
    # async def benchmark_system_fetch():
    #     """Benchmark: Fetch all system records."""
    #     stmt = select(System)
    #     await db_session.execute(stmt)
    # 
    # await benchmark.run(benchmark_market_data_fetch, "market_data_fetch")
    # await benchmark.run(benchmark_market_data_by_symbol, "market_data_by_symbol")
    # await benchmark.run(benchmark_system_fetch, "system_fetch")
    
    return benchmark.get_summary()


async def benchmark_connection_pool(db_engine: Any) -> Dict[str, Any]:
    """Benchmark database connection pool performance."""
    from sqlalchemy.ext.asyncio import AsyncSession
    
    benchmark = QueryBenchmark("connection_pool", iterations=100)
    results = []
    
    async def get_connection():
        async with db_engine.connect() as conn:
            await conn.execute("SELECT 1")
    
    result = await benchmark.run(get_connection, "pool_get_connection")
    results.append(result.to_dict())
    
    return {
        "benchmarks": results,
        "avg_time": results[0]["avg_time"] if results else 0,
    }


async def benchmark_concurrent_queries(
    db_session: Any,
    concurrency: int = 10,
) -> Dict[str, Any]:
    """Run concurrent query benchmarks."""
    
    async def simple_query():
        from sqlalchemy import text
        await db_session.execute(text("SELECT 1"))
    
    # Run queries concurrently
    start = time.perf_counter()
    await asyncio.gather(*[simple_query() for _ in range(concurrency)])
    total_time = time.perf_counter() - start
    
    return {
        "concurrency": concurrency,
        "total_time": total_time,
        "avg_per_query": total_time / concurrency,
        "queries_per_second": concurrency / total_time,
    }


def print_benchmark_results(results: Dict[str, Any]) -> None:
    """Print benchmark results in a readable format."""
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    
    for benchmark in results.get("benchmarks", []):
        print(f"\n{benchmark['name']}:")
        print(f"  Iterations:    {benchmark['iterations']}")
        print(f"  Avg Time:      {benchmark['avg_time']*1000:.3f}ms")
        print(f"  Min Time:      {benchmark['min_time']*1000:.3f}ms")
        print(f"  Max Time:      {benchmark['max_time']*1000:.3f}ms")
        print(f"  Std Dev:       {benchmark['std_dev']*1000:.3f}ms")
        print(f"  Total Time:    {benchmark['total_time']*1000:.3f}ms")
    
    if "fastest" in results:
        print(f"\nFastest:        {results['fastest']}")
        print(f"Slowest:        {results['slowest']}")
    
    print("=" * 60)


# Example usage when run directly
if __name__ == "__main__":
    async def demo():
        """Demo benchmark with mock operations."""
        print("Running benchmark demo...")
        
        benchmark = QueryBenchmark("demo", iterations=10)
        
        async def mock_query():
            await asyncio.sleep(0.01)  # Simulate query time
            return "result"
        
        result = await benchmark.run(mock_query)
        
        print_benchmark_results(benchmark.get_summary())
        
        # Demo concurrent benchmark
        print("\n" + "=" * 60)
        print("CONCURRENT QUERY BENCHMARK")
        print("=" * 60)
        
        concurrent_results = await benchmark_concurrent_queries(None, concurrency=20)
        print(f"Concurrency:     {concurrent_results['concurrency']}")
        print(f"Total Time:      {concurrent_results['total_time']*1000:.3f}ms")
        print(f"Avg/Query:       {concurrent_results['avg_per_query']*1000:.3f}ms")
        print(f"Queries/sec:     {concurrent_results['queries_per_second']:.1f}")
    
    asyncio.run(demo())
