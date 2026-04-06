from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from domains.analytics.archive.export_service import ArchiveExportService
from infra.analytics.clickhouse_client import ClickHouseClient, get_clickhouse_client
from infra.observability.runtime_monitoring import run_runtime_monitored

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ColdStorageWorker:
    def __init__(
        self,
        client: ClickHouseClient | None = None,
        export_service: ArchiveExportService | None = None,
        *,
        tables: tuple[str, ...] = (
            "signal_events",
            "scanner_decision_events",
            "notification_events",
            "receipt_events",
            "trade_events",
            "tradingagents_events",
            "subscription_events",
        ),
        retention_days: int = 30,
    ) -> None:
        self.client = client or get_clickhouse_client()
        self.export_service = export_service or ArchiveExportService(self.client)
        self.tables = tables
        self.retention_days = retention_days
        self._running = False

    async def run_forever(self, poll_interval_seconds: int = 86400) -> None:
        self._running = True
        while self._running:
            await self.archive_old_partitions()
            await asyncio.sleep(poll_interval_seconds)

    async def archive_old_partitions(self) -> dict[str, Any]:
        cutoff = utcnow() - timedelta(days=self.retention_days)
        cutoff_partition = cutoff.strftime("%Y-%m")
        manifests: list[dict[str, Any]] = []
        for table in self.tables:
            partitions = await self.client.list_partitions(table)
            for partition in partitions:
                if not partition:
                    continue
                if partition > cutoff_partition:
                    continue
                if partition == cutoff_partition:
                    rows = await self.export_service.client.query_rows(table)
                    if not any(
                        self._partition_key(row) == partition and self._is_older_than(row, cutoff)
                        for row in rows
                    ):
                        continue
                manifest = await self.export_service.export_partition(table, partition)
                if manifest is not None:
                    manifests.append(manifest)
        return {"archived": len(manifests), "partitions": manifests}

    @staticmethod
    def _partition_key(row: dict[str, Any]) -> str | None:
        for key in ("occurred_at", "as_of_date", "created_at", "recorded_at"):
            value = row.get(key)
            if isinstance(value, str) and len(value) >= 7:
                return value[:7]
        return None

    @staticmethod
    def _is_older_than(row: dict[str, Any], cutoff: datetime) -> bool:
        for key in ("occurred_at", "as_of_date", "created_at", "recorded_at"):
            value = row.get(key)
            if isinstance(value, str) and value:
                timestamp = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
                    timezone.utc
                )
                return timestamp < cutoff
        return False

    def stop(self) -> None:
        self._running = False


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    result = await run_runtime_monitored(
        "cold-storage",
        "worker",
        ColdStorageWorker().archive_old_partitions,
        metadata={"mode": "batch"},
        final_status="completed",
    )
    logger.info("Cold storage archive finished: %s", result)


if __name__ == "__main__":
    asyncio.run(main())
