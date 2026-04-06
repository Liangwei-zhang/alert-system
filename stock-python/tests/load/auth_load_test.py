"""
Load test for authentication endpoints.
Target: 2000 RPS auth burst for 300M DAU capacity.
"""
from locust import HttpUser, task, between, events
import random
import string


class AuthUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """Generate unique user credentials for each virtual user."""
        self.username = f"loadtest_user_{random.randint(1, 100000)}"
        self.email = f"{self.username}@loadtest.local"
        self.password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
    
    @task(10)
    def register(self):
        """Test user registration endpoint."""
        self.client.post(
            "/api/v1/auth/register",
            json={
                "username": self.username,
                "email": self.email,
                "password": self.password,
            },
            name="POST /auth/register"
        )
    
    @task(20)
    def login(self):
        """Test login endpoint - most frequent auth operation."""
        self.client.post(
            "/api/v1/auth/login",
            json={
                "username": self.username,
                "password": self.password,
            },
            name="POST /auth/login"
        )
    
    @task(5)
    def refresh_token(self):
        """Test token refresh endpoint."""
        self.client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "test_refresh_token"},
            name="POST /auth/refresh"
        )
    
    @task(3)
    def verify_token(self):
        """Test token verification endpoint."""
        self.client.get(
            "/api/v1/auth/verify",
            name="GET /auth/verify"
        )


# Event handlers for custom metrics
@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"Starting auth load test...")
    print(f"Target: 2000 RPS auth burst")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"Auth load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")