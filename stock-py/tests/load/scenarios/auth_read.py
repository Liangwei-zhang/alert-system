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
            ok_statuses=(200, 429),
            json={"email": self.auth_email},
        )

    @task(1)
    def refresh_session(self) -> None:
        if not self.refresh_token:
            return
        response = self.post_json(
            "/v1/auth/refresh",
            name="auth.refresh",
            json={"refresh_token": self.refresh_token},
        )
        if response is None or response.status_code != 200:
            return

        try:
            payload = response.json()
        except ValueError:
            return

        next_access_token = str(payload.get("access_token") or "").strip()
        next_refresh_token = str(payload.get("refresh_token") or "").strip()
        if next_access_token:
            self.access_token = next_access_token
        if next_refresh_token:
            self.refresh_token = next_refresh_token
