"""
Load test for scanner/signals simulation.
Target: Simulates scanner operations for 300M DAU capacity.
"""
from locust import HttpUser, task, between, events
import random


# Common stock symbols for scanning simulation
STOCK_SYMBOLS = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "META", "TSLA", "NVDA", "AMD",
    "SPY", "QQQ", "IWM", "DIA", "JPM", "BAC", "WFC", "GS",
    "XOM", "CVX", "COP", "SLB", "UNH", "CVS", "CI", "HUM",
    "JNJ", "PFE", "MRK", "ABBV", "LLY", "TMO", "ABT", "DHR"
]


class ScannerUser(HttpUser):
    wait_time = between(0.5, 2.0)
    
    def on_start(self):
        """Set up for scanner simulation."""
        self.user_id = random.randint(1, 100000)
        self.token = f"test_token_{self.user_id}"
        self.symbols = random.sample(STOCK_SYMBOLS, k=random.randint(5, 15))
    
    @task(30)
    def list_signals(self):
        """Test signals list endpoint - main scanner view."""
        symbol = random.choice(self.symbols) if self.symbols else None
        self.client.get(
            f"/api/v1/signals?symbol={symbol}&limit=50",
            name="GET /signals [list]",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(25)
    def get_active_signals(self):
        """Test active signals endpoint - live scanner results."""
        symbol = random.choice(self.symbols) if self.symbols else None
        self.client.get(
            f"/api/v1/signals/active?symbol={symbol}",
            name="GET /signals/active",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(15)
    def get_signal_stats(self):
        """Test signal statistics endpoint."""
        self.client.get(
            "/api/v1/signals/stats",
            name="GET /signals/stats",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(10)
    def get_signal_by_id(self):
        """Test individual signal retrieval."""
        signal_id = random.randint(1, 10000)
        self.client.get(
            f"/api/v1/signals/{signal_id}",
            name="GET /signals/{id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(8)
    def generate_signal(self):
        """Simulate signal generation from OHLCV data."""
        symbol = random.choice(STOCK_SYMBOLS)
        # Generate synthetic OHLCV data (20+ data points for signal generation)
        n = random.randint(20, 50)
        base_price = random.uniform(50, 500)
        
        import math
        high = [base_price + random.uniform(-10, 20) + math.sin(i/5)*5 for i in range(n)]
        low = [base_price + random.uniform(-20, 10) + math.sin(i/5)*5 for i in range(n)]
        close = [base_price + random.uniform(-15, 15) + math.sin(i/5)*5 for i in range(n)]
        volume = [random.randint(100000, 10000000) for _ in range(n)]
        
        self.client.post(
            "/api/v1/signals/generate",
            json={
                "symbol": symbol,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume,
                "strategy_id": random.randint(1, 5)
            },
            name="POST /signals/generate",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def get_signals_history(self):
        """Test signals history by date range."""
        import datetime
        end = datetime.datetime.now()
        start = end - datetime.timedelta(days=7)
        signal_type = random.choice(["BULLISH", "BEARISH", "NEUTRAL"]) if random.random() > 0.5 else None
        
        params = f"start_date={start.isoformat()}&end_date={end.isoformat()}"
        if signal_type:
            params += f"&signal_type={signal_type}"
        
        self.client.get(
            f"/api/v1/signals/history/range?{params}",
            name="GET /signals/history/range",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(4)
    def create_manual_signal(self):
        """Test manual signal creation."""
        stock_id = random.randint(1, 1000)
        self.client.post(
            "/api/v1/signals/",
            json={
                "stock_id": stock_id,
                "signal_type": random.choice(["BUY", "SELL"]),
                "entry_price": random.uniform(50, 500),
                "stop_loss": random.uniform(40, 450),
                "take_profit_1": random.uniform(60, 550),
                "reasoning": "Load test signal"
            },
            name="POST /signals/",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(3)
    def update_signal(self):
        """Test signal update endpoint."""
        signal_id = random.randint(1, 10000)
        self.client.patch(
            f"/api/v1/signals/{signal_id}",
            json={
                "status": random.choice(["ACTIVE", "TRIGGERED", "EXPIRED"]),
                "stop_loss": random.uniform(40, 450)
            },
            name="PATCH /signals/{id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"Starting scanner/signals load test...")
    print(f"Target: Scanner simulation for 300M DAU")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"Scanner load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")