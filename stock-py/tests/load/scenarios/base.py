from __future__ import annotations

import os
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from locust import HttpUser, between


class ApiUser(HttpUser):
    abstract = True
    wait_time = between(1, 3)

    def on_start(self) -> None:
        self.access_token = os.getenv("LOAD_TEST_ACCESS_TOKEN", "")
        self.refresh_token = os.getenv("LOAD_TEST_REFRESH_TOKEN", "")
        self.auth_email = os.getenv("LOAD_TEST_AUTH_EMAIL", "loadtest@example.com")
        self.notification_limit = int(os.getenv("LOAD_TEST_NOTIFICATION_LIMIT", "20"))
        self.trade_id = os.getenv("LOAD_TEST_TRADE_ID", "trade-1")
        self.trade_token = os.getenv("LOAD_TEST_TRADE_TOKEN", "")
        self.enable_trade_mutations = os.getenv(
            "LOAD_TEST_ENABLE_TRADE_MUTATIONS", "false"
        ).lower() in {
            "1",
            "true",
            "yes",
        }
        self.tradingagents_ticker = os.getenv("LOAD_TEST_TRADINGAGENTS_TICKER", "AAPL").upper()
        analysts = os.getenv("LOAD_TEST_TRADINGAGENTS_ANALYSTS", "alpha,beta")
        self.tradingagents_analysts = [item.strip() for item in analysts.split(",") if item.strip()]
        self.tradingagents_trigger_type = os.getenv(
            "LOAD_TEST_TRADINGAGENTS_TRIGGER_TYPE", "load_test"
        )
        self.tradingagents_trigger_source = os.getenv(
            "LOAD_TEST_TRADINGAGENTS_TRIGGER_SOURCE", "locust"
        )

    def bearer_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        name: str,
        ok_statuses: Sequence[int] = (200,),
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> None:
        request_method = getattr(self.client, method)
        with request_method(
            path,
            name=name,
            headers=dict(headers or {}),
            params=params,
            json=json,
            catch_response=True,
        ) as response:
            if response.status_code not in ok_statuses:
                response.failure(
                    f"unexpected status {response.status_code}, expected {tuple(ok_statuses)}: {response.text[:300]}"
                )

    def get_json(
        self,
        path: str,
        *,
        name: str,
        ok_statuses: Sequence[int] = (200,),
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
    ) -> None:
        self._request(
            "get",
            path,
            name=name,
            ok_statuses=ok_statuses,
            headers=headers,
            params=params,
        )

    def post_json(
        self,
        path: str,
        *,
        name: str,
        ok_statuses: Sequence[int] = (200,),
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> None:
        self._request(
            "post",
            path,
            name=name,
            ok_statuses=ok_statuses,
            headers=headers,
            params=params,
            json=json,
        )

    def next_request_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def utc_now_iso() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
