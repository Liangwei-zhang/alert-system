from __future__ import annotations

from locust import task

from tests.load.scenarios.base import ApiUser


class TradeActionUser(ApiUser):
    weight = 2

    @task(4)
    def read_app_trade(self) -> None:
        headers = self.bearer_headers()
        if not headers:
            return
        self.get_json(
            f"/v1/trades/{self.trade_id}/app-info",
            name="trades.app_info",
            headers=headers,
        )

    @task(2)
    def read_public_trade(self) -> None:
        if not self.trade_token:
            return
        self.get_json(
            f"/v1/trades/{self.trade_id}/info",
            name="trades.public_info",
            params={"t": self.trade_token},
        )

    @task(1)
    def confirm_trade(self) -> None:
        if not self.enable_trade_mutations:
            return
        headers = self.bearer_headers()
        if not headers:
            return
        self.post_json(
            f"/v1/trades/{self.trade_id}/app-confirm",
            name="trades.app_confirm",
            headers=headers,
        )
