from __future__ import annotations

from locust import task

from tests.load.scenarios.base import ApiUser


class NotificationReaderUser(ApiUser):
    weight = 3

    @task(3)
    def list_notifications(self) -> None:
        headers = self.bearer_headers()
        if not headers:
            return
        self.get_json(
            "/v1/notifications",
            name="notifications.list",
            headers=headers,
            params={"limit": self.notification_limit},
        )

    @task(1)
    def list_push_devices(self) -> None:
        headers = self.bearer_headers()
        if not headers:
            return
        self.get_json(
            "/v1/notifications/push-devices",
            name="notifications.push_devices",
            headers=headers,
        )
