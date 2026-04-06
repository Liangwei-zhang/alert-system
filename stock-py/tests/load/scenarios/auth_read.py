from __future__ import annotations

from locust import task

from tests.load.scenarios.base import ApiUser


class AuthReadUser(ApiUser):
    weight = 2

    @task(3)
    def send_code(self) -> None:
        self.post_json(
            "/v1/auth/send-code",
            name="auth.send_code",
            json={"email": self.auth_email},
        )

    @task(1)
    def refresh_session(self) -> None:
        if not self.refresh_token:
            return
        self.post_json(
            "/v1/auth/refresh",
            name="auth.refresh",
            json={"refresh_token": self.refresh_token},
        )
