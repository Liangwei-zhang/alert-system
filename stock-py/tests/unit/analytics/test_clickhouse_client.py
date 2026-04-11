import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from infra.analytics.clickhouse_client import ClickHouseClient, ClickHouseHttpBackend


class ClickHouseClientTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.client = ClickHouseClient(root_path=self.tempdir.name)

    async def test_insert_query_and_truncate_table(self) -> None:
        now = datetime.now(timezone.utc)
        await self.client.insert_rows(
            "signal_events",
            [
                {"occurred_at": now - timedelta(hours=2), "symbol": "AAPL", "score": 0.4},
                {"occurred_at": now, "symbol": "MSFT", "score": 0.9},
            ],
        )

        rows = await self.client.query_rows("signal_events", start_at=now - timedelta(minutes=5))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "MSFT")

        await self.client.execute("TRUNCATE TABLE signal_events")
        self.assertEqual(await self.client.query_rows("signal_events"), [])

    async def test_query_rows_supports_filters_and_ordering(self) -> None:
        now = datetime.now(timezone.utc)
        await self.client.insert_rows(
            "notification_events",
            [
                {
                    "occurred_at": now - timedelta(minutes=3),
                    "event_type": "requested",
                    "channel": "email",
                },
                {
                    "occurred_at": now - timedelta(minutes=2),
                    "event_type": "requested",
                    "channel": "push",
                },
                {
                    "occurred_at": now - timedelta(minutes=1),
                    "event_type": "delivered",
                    "channel": "push",
                },
            ],
        )

        rows = await self.client.query_rows(
            "notification_events",
            filters={"event_type": "requested"},
            order_by="occurred_at",
            descending=True,
            limit=1,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["channel"], "push")

    async def test_insert_rows_partitions_files_by_month(self) -> None:
        january = datetime(2026, 1, 15, tzinfo=timezone.utc)
        february = datetime(2026, 2, 3, tzinfo=timezone.utc)

        await self.client.insert_rows(
            "trade_events",
            [
                {"occurred_at": january, "trade_id": "T-1", "action": "buy"},
                {"occurred_at": february, "trade_id": "T-2", "action": "sell"},
            ],
        )

        table_dir = Path(self.tempdir.name) / "trade_events"
        self.assertEqual(
            sorted(path.name for path in table_dir.glob("*.jsonl")),
            ["2026-01.jsonl", "2026-02.jsonl"],
        )
        self.assertEqual(await self.client.list_partitions("trade_events"), ["2026-01", "2026-02"])

        rows = await self.client.query_rows("trade_events", start_at=february - timedelta(days=1))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["trade_id"], "T-2")


class ClickHouseHttpBackendErrorHandlingTest(unittest.TestCase):
    def _status_error(
        self,
        *,
        status_code: int,
        text: str,
        exception_code: str | None = None,
    ) -> httpx.HTTPStatusError:
        request = httpx.Request("POST", "http://clickhouse.local/")
        headers = {}
        if exception_code is not None:
            headers["X-ClickHouse-Exception-Code"] = exception_code
        response = httpx.Response(status_code=status_code, text=text, request=request, headers=headers)
        return httpx.HTTPStatusError("query failed", request=request, response=response)

    def test_is_missing_entity_error_recognizes_unknown_table(self) -> None:
        error = self._status_error(
            status_code=404,
            text="Code: 60. DB::Exception: Table stock_py.events does not exist. (UNKNOWN_TABLE)",
        )

        self.assertTrue(ClickHouseHttpBackend._is_missing_entity_error(error))

    def test_is_missing_entity_error_recognizes_unknown_database(self) -> None:
        error = self._status_error(
            status_code=404,
            text="Code: 81. DB::Exception: Database stock_py does not exist. (UNKNOWN_DATABASE)",
        )

        self.assertTrue(ClickHouseHttpBackend._is_missing_entity_error(error))

    def test_is_missing_entity_error_uses_exception_code_header(self) -> None:
        error = self._status_error(
            status_code=404,
            text="some gateway message without canonical marker",
            exception_code="81",
        )

        self.assertTrue(ClickHouseHttpBackend._is_missing_entity_error(error))

    def test_is_missing_entity_error_ignores_auth_failures(self) -> None:
        error = self._status_error(
            status_code=403,
            text="Code: 516. DB::Exception: Authentication failed. (AUTHENTICATION_FAILED)",
            exception_code="516",
        )

        self.assertFalse(ClickHouseHttpBackend._is_missing_entity_error(error))


if __name__ == "__main__":
    unittest.main()
