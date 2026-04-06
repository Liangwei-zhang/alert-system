"""
Load test for notifications endpoints.
Target: 1000 RPS notifications for 300M DAU capacity.
"""
from locust import HttpUser, task, between, events
import random


class NotificationUser(HttpUser):
    wait_time = between(0.2, 0.8)
    
    def on_start(self):
        """Set up authenticated session for notifications."""
        self.user_id = random.randint(1, 100000)
        self.token = f"test_token_{self.user_id}"
    
    @task(25)
    def get_notifications(self):
        """Test notification list endpoint - most frequent operation."""
        self.client.get(
            f"/api/v1/notifications?user_id={self.user_id}",
            name="GET /notifications [list]",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(20)
    def get_unread(self):
        """Test unread notifications endpoint."""
        self.client.get(
            f"/api/v1/notifications/unread?user_id={self.user_id}",
            name="GET /notifications/unread",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(15)
    def get_unread_count(self):
        """Test unread count endpoint."""
        self.client.get(
            f"/api/v1/notifications/unread/count?user_id={self.user_id}",
            name="GET /notifications/unread/count",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(10)
    def mark_read(self):
        """Test mark notification as read."""
        notif_id = random.randint(1, 10000)
        self.client.put(
            f"/api/v1/notifications/{notif_id}/read",
            name="PUT /notifications/{id}/read",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(10)
    def mark_all_read(self):
        """Test mark all as read."""
        self.client.put(
            f"/api/v1/notifications/read-all?user_id={self.user_id}",
            name="PUT /notifications/read-all",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def delete_notification(self):
        """Test delete notification."""
        notif_id = random.randint(1, 10000)
        self.client.delete(
            f"/api/v1/notifications/{notif_id}?user_id={self.user_id}",
            name="DELETE /notifications/{id}",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def register_device(self):
        """Test device registration for push notifications."""
        self.client.post(
            "/api/v1/webpush/register",
            json={
                "user_id": self.user_id,
                "endpoint": f"https://push.example.com/{random.randint(1,10000)}",
                "keys": {
                    "p256dh": "test_key",
                    "auth": "test_auth"
                }
            },
            name="POST /webpush/register",
            headers={"Authorization": f"Bearer {self.token}"}
        )
    
    @task(5)
    def subscribe(self):
        """Test subscription endpoint."""
        self.client.post(
            "/api/v1/notifications/subscribe",
            json={
                "user_id": self.user_id,
                "channels": ["price_alerts", "news", "signals"]
            },
            name="POST /notifications/subscribe",
            headers={"Authorization": f"Bearer {self.token}"}
        )


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print(f"Starting notifications load test...")
    print(f"Target: 1000 RPS notifications")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    print(f"Notifications load test completed")
    print(f"Total requests: {environment.stats.total.num_requests}")
    print(f"Failures: {environment.stats.total.num_failures}")