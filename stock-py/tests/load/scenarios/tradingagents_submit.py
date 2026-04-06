from __future__ import annotations

from locust import task

from tests.load.scenarios.base import ApiUser


class TradingAgentsSubmitUser(ApiUser):
    weight = 1

    @task
    def submit_analysis(self) -> None:
        self.post_json(
            "/v1/internal/tradingagents/submit",
            name="tradingagents.submit",
            json={
                "request_id": self.next_request_id("load"),
                "ticker": self.tradingagents_ticker,
                "analysis_date": self.utc_now_iso(),
                "selected_analysts": self.tradingagents_analysts,
                "trigger_type": self.tradingagents_trigger_type,
                "trigger_context": {
                    "source": self.tradingagents_trigger_source,
                    "channel": "locust",
                },
            },
        )
