"""
Load test for portfolio read endpoints.
Target: 5000 RPS dashboard read for 300M DAU capacity.
"""
from locust import HttpUser, task, between, events
import random


class PortfolioUser(HttpUser):
    wait_time = between(0.05, 0.2)
    
    def on_start(self):
        """Set up authenticated session for portfolio access."""
        self.user_id = random.randint(1, 100000)
        self.token = f"test_token_{self.user_id}"
    
    @task(30)
    def get_portfolio(self):
        """Test main portfolio dashboard endpoint - highest traffic."""
        self.client.get(
            f"/api/v1/portfolio?user_id={self.user_id}",
            name="GET /portfolio [dashboard]",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(20)
    def get_holdings(self):
        """Test holdings list endpoint."""
        self.client.get(
            f"/api/v1/portfolio/holdings?user_id={self.user_id}",
            name="GET /portfolio/holdings",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(15)
    def get_positions(self):
        """Test positions endpoint."""
        self.client.get(
            f"/api/v1/portfolio/positions?user_id={self.user_id}",
            name="GET /portfolio/positions",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(10)
    def get_performance(self):
        """Test performance/metrics endpoint."""
        self.client.get(
            f"/api/v1/portfolio/performance?user_id={self.user_id}",
            name="GET /portfolio/performance",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def get_allocation(self):
        """Test asset allocation endpoint."""
        self.client.get(
            f"/api/v1/portfolio/allocation?user_id={self.user_id}",
            name="GET /portfolio/allocation",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def get_history(self):
        """Test portfolio history endpoint."""
        self.client.get(
            f"/api/v1/portfolio/history?user_id={self.user_id}&days=30",
            name="GET /portfolio/history",
            headers={"Authorization": f"Bearer {self.token}"}
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"Starting portfolio load test...")
    print(f"Target: 5000 RPS dashboard read")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"Portfolio load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")