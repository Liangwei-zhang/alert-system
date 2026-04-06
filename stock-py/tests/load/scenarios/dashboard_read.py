from __future__ import annotations

from locust import task

from tests.load.scenarios.base import ApiUser


class DashboardReadUser(ApiUser):
    weight = 4

    @task(3)
    def read_dashboard(self) -> None:
        headers = self.bearer_headers()
        if not headers:
            return
        self.get_json(
            "/v1/account/dashboard",
            name="account.dashboard",
            headers=headers,
        )

    @task(1)
    def read_profile(self) -> None:
        headers = self.bearer_headers()
        if not headers:
            return
        self.get_json(
            "/v1/account/profile",
            name="account.profile",
            headers=headers,
        )
